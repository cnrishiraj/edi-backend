"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { 
  Send, 
  Bot, 
  User, 
  FileText, 
  MessageCircle,
  Loader2,
  AlertCircle,
  Lightbulb,
  BarChart3
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import Chat from "./Chat";

interface ChatPanelProps {
  fileId: string | null;
  conversationId: string | null;
  onConversationSelect: (conversationId: string) => void;
  onMappingRequest: (fileId: string) => void;
}

interface Conversation {
  id: string;
  title: string;
  file_id: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface QuickAction {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  prompt: string;
  requiresFile: boolean;
}

const quickActions: QuickAction[] = [
  {
    id: 'analyze-file',
    label: 'Analyze File Structure',
    description: 'Get an overview of the uploaded file structure and contents',
    icon: <FileText className="h-4 w-4" />,
    prompt: 'Please analyze the structure and contents of this file. What fields are present and what insights can you provide?',
    requiresFile: true
  },
  {
    id: 'data-quality',
    label: 'Check Data Quality',
    description: 'Identify potential data quality issues and inconsistencies',
    icon: <AlertCircle className="h-4 w-4" />,
    prompt: 'Please perform a data quality analysis on this file. Check for missing values, inconsistencies, and potential issues.',
    requiresFile: true
  },
  {
    id: 'mapping-suggestions',
    label: 'Suggest Field Mappings',
    description: 'Get AI-powered suggestions for field mappings to VBA schema',
    icon: <Lightbulb className="h-4 w-4" />,
    prompt: 'Based on this SmithRx claims file, what field mappings would you recommend for the VBA schema? Please provide specific mapping suggestions.',
    requiresFile: true
  },
  {
    id: 'data-summary',
    label: 'Summarize Data',
    description: 'Get a high-level summary of the data and key statistics',
    icon: <BarChart3 className="h-4 w-4" />,
    prompt: 'Please provide a comprehensive summary of this data including key statistics, trends, and important insights.',
    requiresFile: true
  }
];

export default function ChatPanel({ 
  fileId, 
  conversationId, 
  onConversationSelect,
  onMappingRequest 
}: ChatPanelProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(conversationId);
  const [isIndexingFile, setIsIndexingFile] = useState(false);
  const [fileIndexed, setFileIndexed] = useState(false);
  const { toast } = useToast();

  // Load conversations when component mounts or fileId changes
  useEffect(() => {
    loadConversations();
  }, [fileId]);

  // Update active conversation when prop changes
  useEffect(() => {
    setActiveConversationId(conversationId);
  }, [conversationId]);

  // Check if file is indexed for AI chat
  useEffect(() => {
    if (fileId) {
      checkFileIndexStatus();
    }
  }, [fileId]);

  const loadConversations = async () => {
    setIsLoadingConversations(true);
    try {
      const params = new URLSearchParams();
      if (fileId) params.append('file_id', fileId);
      params.append('limit', '10');

      const response = await fetch(`http://localhost:8000/api/v1/chat/conversations?${params}`);
      if (response.ok) {
        const conversationsData = await response.json();
        setConversations(conversationsData);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
      toast({
        title: "Failed to load conversations",
        description: "Could not load chat history",
        variant: "destructive",
      });
    } finally {
      setIsLoadingConversations(false);
    }
  };

  const checkFileIndexStatus = async () => {
    if (!fileId) return;

    try {
      const response = await fetch(`http://localhost:8000/api/v1/files/${fileId}/status`);
      if (response.ok) {
        const fileData = await response.json();
        // Check if file has been indexed (this would be a custom field in the real implementation)
        setFileIndexed(fileData.processing_status === 'indexed' || fileData.processing_status === 'completed');
      }
    } catch (error) {
      console.error('Failed to check file index status:', error);
    }
  };

  const indexFileForChat = async () => {
    if (!fileId) return;

    setIsIndexingFile(true);
    try {
      const response = await fetch(`http://localhost:8000/api/v1/chat/index/${fileId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      if (response.ok) {
        const result = await response.json();
        toast({
          title: "File indexing started",
          description: `${result.message}. Estimated time: ${result.estimated_time_minutes} minutes`,
        });

        // Poll for completion (simplified for POC)
        setTimeout(() => {
          setFileIndexed(true);
          setIsIndexingFile(false);
          toast({
            title: "File indexed successfully",
            description: "You can now chat with your data using AI",
          });
        }, 3000);
      } else {
        throw new Error('Failed to start indexing');
      }
    } catch (error) {
      console.error('Failed to index file:', error);
      toast({
        title: "Failed to index file",
        description: "Could not prepare file for AI chat",
        variant: "destructive",
      });
      setIsIndexingFile(false);
    }
  };

  const handleQuickAction = (action: QuickAction) => {
    if (action.requiresFile && !fileId) {
      toast({
        title: "File required",
        description: "Please select a file first to use this action",
        variant: "destructive",
      });
      return;
    }

    // This will be handled by the Chat component
    // For now, we'll just show which action was selected
    console.log('Quick action selected:', action.label, action.prompt);
  };

  const handleConversationClick = (conversation: Conversation) => {
    setActiveConversationId(conversation.id);
    onConversationSelect(conversation.id);
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    onConversationSelect('');
  };

  return (
    <div className="h-full flex flex-col">
      
      {/* Chat Header & Controls */}
      <div className="space-y-3 mb-4">
        
        {/* File Status */}
        {fileId && (
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <FileText className="h-4 w-4 text-blue-500" />
                  <span className="text-sm font-medium">File: {fileId.slice(0, 8)}...</span>
                  {fileIndexed ? (
                    <Badge variant="default" className="text-xs">Ready for AI Chat</Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs">Not Indexed</Badge>
                  )}
                </div>
                
                {!fileIndexed && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={indexFileForChat}
                    disabled={isIndexingFile}
                  >
                    {isIndexingFile ? (
                      <>
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        Indexing...
                      </>
                    ) : (
                      'Enable AI Chat'
                    )}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Quick Actions */}
        {fileId && fileIndexed && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                {quickActions.map((action) => (
                  <Button
                    key={action.id}
                    variant="outline"
                    size="sm"
                    className="h-auto p-2 text-left justify-start"
                    onClick={() => handleQuickAction(action)}
                    disabled={action.requiresFile && !fileId}
                  >
                    <div className="flex flex-col items-start space-y-1">
                      <div className="flex items-center space-x-1">
                        {action.icon}
                        <span className="text-xs font-medium">{action.label}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {action.description}
                      </span>
                    </div>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Conversation History */}
        {conversations.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                Recent Conversations
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNewConversation}
                >
                  New Chat
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-20">
                <div className="space-y-1">
                  {conversations.map((conversation) => (
                    <Button
                      key={conversation.id}
                      variant={activeConversationId === conversation.id ? "default" : "ghost"}
                      size="sm"
                      className="w-full justify-start text-left"
                      onClick={() => handleConversationClick(conversation)}
                    >
                      <MessageCircle className="h-3 w-3 mr-2" />
                      <span className="truncate text-xs">
                        {conversation.title || `Chat ${conversation.id.slice(0, 8)}`}
                      </span>
                      <Badge variant="secondary" className="ml-auto text-xs">
                        {conversation.message_count}
                      </Badge>
                    </Button>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        )}
      </div>

      <Separator className="my-2" />

      {/* Main Chat Interface */}
      <div className="flex-1 overflow-hidden">
        {!fileId ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center space-y-2">
              <Bot className="h-12 w-12 mx-auto text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Select a file to start chatting with your data
              </p>
            </div>
          </div>
        ) : !fileIndexed ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center space-y-4">
              <AlertCircle className="h-12 w-12 mx-auto text-amber-500" />
              <div>
                <p className="text-sm font-medium mb-1">
                  File needs to be indexed for AI chat
                </p>
                <p className="text-xs text-muted-foreground mb-3">
                  Click "Enable AI Chat" above to prepare your file for analysis
                </p>
                <Button onClick={indexFileForChat} disabled={isIndexingFile}>
                  {isIndexingFile ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Indexing File...
                    </>
                  ) : (
                    'Enable AI Chat'
                  )}
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <Chat
            fileId={fileId}
            conversationId={activeConversationId}
            onConversationCreate={(newConversationId) => {
              setActiveConversationId(newConversationId);
              onConversationSelect(newConversationId);
              loadConversations(); // Refresh conversation list
            }}
            onMappingRequest={onMappingRequest}
            quickActions={quickActions}
          />
        )}
      </div>
    </div>
  );
}