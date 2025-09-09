"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { 
  Send, 
  Bot, 
  User, 
  Loader2, 
  Copy,
  ThumbsUp,
  ThumbsDown,
  CornerDownLeft,
  AlertCircle
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { formatDistanceToNow } from 'date-fns';

interface ChatProps {
  fileId: string | null;
  conversationId: string | null;
  onConversationCreate: (conversationId: string) => void;
  onMappingRequest: (fileId: string) => void;
  quickActions: Array<{
    id: string;
    label: string;
    prompt: string;
    requiresFile: boolean;
  }>;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  conversation_id: string;
  message_metadata?: {
    tokens?: number;
    response_time?: number;
    sources?: string[];
    confidence?: number;
  };
}

interface StreamingMessage {
  id: string;
  content: string;
  isComplete: boolean;
  error?: string;
}

export default function Chat({ 
  fileId, 
  conversationId, 
  onConversationCreate,
  onMappingRequest,
  quickActions 
}: ChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(conversationId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const { toast } = useToast();

  // Load conversation messages when conversationId changes
  useEffect(() => {
    if (conversationId && conversationId !== currentConversationId) {
      loadConversationMessages(conversationId);
      setCurrentConversationId(conversationId);
    } else if (!conversationId) {
      setMessages([]);
      setCurrentConversationId(null);
    }
  }, [conversationId]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  // Focus input when component mounts
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const loadConversationMessages = async (convId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/chat/conversations/${convId}`);
      if (response.ok) {
        const conversationData = await response.json();
        setMessages(conversationData.messages || []);
      }
    } catch (error) {
      console.error('Failed to load conversation messages:', error);
      toast({
        title: "Failed to load messages",
        description: "Could not load conversation history",
        variant: "destructive",
      });
    }
  };

  const sendMessage = async (messageContent?: string) => {
    const content = messageContent || input.trim();
    if (!content || isStreaming) return;

    if (!messageContent) setInput("");
    
    // Add user message to UI immediately
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
      conversation_id: currentConversationId || ''
    };

    setMessages(prev => [...prev, userMessage]);
    setIsStreaming(true);

    try {
      // Create abort controller for cancelling requests
      abortControllerRef.current = new AbortController();

      // Prepare request body
      const requestBody = {
        message: content,
        conversation_id: currentConversationId,
        file_id: fileId,
        temperature: 0.7,
        max_tokens: 1000
      };

      // Start streaming chat
      const response = await fetch('http://localhost:8000/api/v1/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      // Process streaming response
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';
      let assistantMessageId = '';
      let newConversationId = currentConversationId;

      setStreamingMessage({
        id: 'streaming',
        content: '',
        isComplete: false
      });

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.conversation_id && !newConversationId) {
                newConversationId = data.conversation_id;
                setCurrentConversationId(newConversationId);
                onConversationCreate(newConversationId);
              }

              if (data.message_id) {
                assistantMessageId = data.message_id;
              }

              if (data.content) {
                assistantMessage += data.content;
                setStreamingMessage({
                  id: 'streaming',
                  content: assistantMessage,
                  isComplete: false
                });
              }

              if (data.is_complete) {
                // Streaming complete
                const finalAssistantMessage: ChatMessage = {
                  id: assistantMessageId || `assistant-${Date.now()}`,
                  role: 'assistant',
                  content: assistantMessage,
                  timestamp: new Date().toISOString(),
                  conversation_id: newConversationId || '',
                  message_metadata: {
                    response_time: Date.now() - parseInt(userMessage.id.split('-')[1]),
                    tokens: assistantMessage.split(' ').length
                  }
                };

                setMessages(prev => [...prev, finalAssistantMessage]);
                setStreamingMessage(null);
                break;
              }

              if (data.event_type === 'error') {
                throw new Error(data.content || 'Stream error');
              }

            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError);
            }
          }
        }
      }

    } catch (error: any) {
      console.error('Chat error:', error);
      
      if (error.name === 'AbortError') {
        toast({
          title: "Message cancelled",
          description: "The message was cancelled",
        });
      } else {
        toast({
          title: "Chat error",
          description: error.message || "Failed to send message",
          variant: "destructive",
        });

        // Add error message
        const errorMessage: ChatMessage = {
          id: `error-${Date.now()}`,
          role: 'system',
          content: `Error: ${error.message || 'Failed to send message'}`,
          timestamp: new Date().toISOString(),
          conversation_id: currentConversationId || ''
        };

        setMessages(prev => [...prev, errorMessage]);
      }

      setStreamingMessage(null);
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const cancelMessage = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const copyMessage = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast({
        title: "Copied to clipboard",
        description: "Message content copied",
      });
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const addMessageFeedback = async (messageId: string, feedback: 'helpful' | 'not_helpful') => {
    try {
      await fetch(`http://localhost:8000/api/v1/chat/messages/${messageId}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          helpful: feedback === 'helpful',
          rating: feedback === 'helpful' ? 5 : 1
        }),
      });

      toast({
        title: "Feedback recorded",
        description: "Thank you for your feedback",
      });
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  const handleQuickAction = (prompt: string) => {
    sendMessage(prompt);
  };

  const renderMessage = (message: ChatMessage) => (
    <div key={message.id} className="flex space-x-3 mb-4">
      <Avatar className="h-8 w-8">
        <AvatarFallback className={
          message.role === 'assistant' ? 'bg-blue-100 text-blue-600' :
          message.role === 'system' ? 'bg-red-100 text-red-600' :
          'bg-green-100 text-green-600'
        }>
          {message.role === 'assistant' ? <Bot className="h-4 w-4" /> :
           message.role === 'system' ? <AlertCircle className="h-4 w-4" /> :
           <User className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center space-x-2 mb-1">
          <span className="text-sm font-medium">
            {message.role === 'assistant' ? 'AI Assistant' : 
             message.role === 'system' ? 'System' : 'You'}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
          </span>
          {message.message_metadata?.confidence && (
            <Badge variant="outline" className="text-xs">
              {Math.round(message.message_metadata.confidence * 100)}% confident
            </Badge>
          )}
        </div>
        
        <div className={`
          text-sm leading-relaxed whitespace-pre-wrap break-words
          ${message.role === 'system' ? 'text-red-600' : 'text-foreground'}
        `}>
          {message.content}
        </div>

        {message.message_metadata?.sources && (
          <div className="mt-2">
            <p className="text-xs text-muted-foreground mb-1">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {message.message_metadata.sources.map((source, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {source}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center space-x-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => copyMessage(message.content)}
          >
            <Copy className="h-3 w-3" />
          </Button>
          
          {message.role === 'assistant' && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => addMessageFeedback(message.id, 'helpful')}
              >
                <ThumbsUp className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => addMessageFeedback(message.id, 'not_helpful')}
              >
                <ThumbsDown className="h-3 w-3" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );

  const renderStreamingMessage = () => {
    if (!streamingMessage) return null;

    return (
      <div className="flex space-x-3 mb-4">
        <Avatar className="h-8 w-8">
          <AvatarFallback className="bg-blue-100 text-blue-600">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-sm font-medium">AI Assistant</span>
            <Badge variant="outline" className="text-xs animate-pulse">
              Thinking...
            </Badge>
          </div>
          
          <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {streamingMessage.content}
            <span className="animate-pulse">|</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      
      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.length === 0 && !streamingMessage ? (
            <div className="text-center space-y-4 mt-8">
              <Bot className="h-16 w-16 mx-auto text-muted-foreground" />
              <div>
                <h3 className="text-lg font-medium mb-2">Start a conversation</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {fileId 
                    ? "Ask questions about your data or use one of the quick actions below"
                    : "Upload a file first to chat with your data"
                  }
                </p>
                
                {/* Quick Actions */}
                {fileId && quickActions.length > 0 && (
                  <div className="grid grid-cols-1 gap-2 max-w-md mx-auto">
                    {quickActions.map((action) => (
                      <Button
                        key={action.id}
                        variant="outline"
                        size="sm"
                        className="text-left justify-start"
                        onClick={() => handleQuickAction(action.prompt)}
                        disabled={!fileId && action.requiresFile}
                      >
                        {action.label}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="group">
              {messages.map(renderMessage)}
              {renderStreamingMessage()}
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t p-4">
        <div className="flex space-x-2">
          <div className="flex-1 relative">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                fileId 
                  ? "Ask a question about your data..." 
                  : "Upload a file to start chatting..."
              }
              disabled={!fileId || isStreaming}
              className="pr-8"
            />
            {input && (
              <div className="absolute right-2 top-1/2 -translate-y-1/2">
                <kbd className="text-xs bg-muted px-1 py-0.5 rounded">
                  <CornerDownLeft className="h-3 w-3" />
                </kbd>
              </div>
            )}
          </div>
          
          <Button
            onClick={() => sendMessage()}
            disabled={!input.trim() || !fileId || isStreaming}
            size="sm"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>

          {isStreaming && (
            <Button
              onClick={cancelMessage}
              variant="outline"
              size="sm"
            >
              Cancel
            </Button>
          )}
        </div>
        
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {fileId 
              ? `Chatting with file: ${fileId.slice(0, 8)}...`
              : "No file selected"
            }
          </span>
          {messages.length > 0 && (
            <span>
              {messages.length} message{messages.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}