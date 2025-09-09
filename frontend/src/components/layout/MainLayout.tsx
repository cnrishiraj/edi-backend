"use client";

import { useState, useEffect } from "react";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FileText, MessageCircle, GitBranch, RefreshCw } from "lucide-react";
import FileUploadPanel from "../FileUploadPanel";
import ChatPanel from "../ChatPanel";
import MappingPanel from "../MappingPanel";

interface MainLayoutProps {
  children?: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [activeMappingId, setActiveMappingId] = useState<string | null>(null);
  const [systemStatus, setSystemStatus] = useState({
    backend: 'checking',
    files: 0,
    conversations: 0,
    mappings: 0
  });

  // Check backend connectivity and system status
  useEffect(() => {
    const checkSystemStatus = async () => {
      try {
        const response = await fetch('http://localhost:8000/health');
        if (response.ok) {
          setSystemStatus(prev => ({ ...prev, backend: 'connected' }));
          
          // Get counts for dashboard
          const [filesRes, conversationsRes, mappingsRes] = await Promise.all([
            fetch('http://localhost:8000/api/v1/files?limit=1'),
            fetch('http://localhost:8000/api/v1/chat/conversations?limit=1'),
            fetch('http://localhost:8000/api/v1/mappings?limit=1')
          ]);
          
          // Note: In a real app, you'd want proper count endpoints
          // For now, this gives us basic connectivity verification
        } else {
          setSystemStatus(prev => ({ ...prev, backend: 'error' }));
        }
      } catch (error) {
        setSystemStatus(prev => ({ ...prev, backend: 'disconnected' }));
      }
    };

    checkSystemStatus();
    const interval = setInterval(checkSystemStatus, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  const handleFileSelect = (fileId: string) => {
    setSelectedFileId(fileId);
    // Auto-create or find conversation for this file
    // This would typically make an API call to get/create conversation
  };

  const handleConversationSelect = (conversationId: string) => {
    setActiveConversationId(conversationId);
  };

  const handleMappingSelect = (mappingId: string) => {
    setActiveMappingId(mappingId);
  };

  const refreshSystem = () => {
    // Trigger refresh of all panels
    window.location.reload(); // Simple refresh for POC
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="border-b bg-card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold text-foreground">
              EDI Healthcare Data Integration POC
            </h1>
            <Badge 
              variant={systemStatus.backend === 'connected' ? 'default' : 'destructive'}
              className="text-xs"
            >
              {systemStatus.backend === 'connected' ? '🟢 Backend Connected' : 
               systemStatus.backend === 'checking' ? '🟡 Checking...' : 
               '🔴 Backend Disconnected'}
            </Badge>
          </div>
          
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={refreshSystem}
              className="text-xs"
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content - 3 Panel Layout */}
      <main className="flex-1 p-4">
        <ResizablePanelGroup direction="horizontal" className="h-full rounded-lg border">
          
          {/* Panel 1: File Upload & Management */}
          <ResizablePanel defaultSize={30} minSize={25} maxSize={40}>
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center text-lg">
                  <FileText className="h-5 w-5 mr-2 text-blue-500" />
                  File Management
                </CardTitle>
              </CardHeader>
              <CardContent className="h-[calc(100%-80px)] overflow-hidden">
                <FileUploadPanel
                  selectedFileId={selectedFileId}
                  onFileSelect={handleFileSelect}
                  onFileProcessed={(fileId) => {
                    setSelectedFileId(fileId);
                  }}
                />
              </CardContent>
            </Card>
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* Panel 2: AI Chat Interface */}
          <ResizablePanel defaultSize={35} minSize={30} maxSize={45}>
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center text-lg">
                  <MessageCircle className="h-5 w-5 mr-2 text-green-500" />
                  AI Assistant
                  {selectedFileId && (
                    <Badge variant="secondary" className="ml-2 text-xs">
                      File Selected
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="h-[calc(100%-80px)] overflow-hidden">
                <ChatPanel
                  fileId={selectedFileId}
                  conversationId={activeConversationId}
                  onConversationSelect={handleConversationSelect}
                  onMappingRequest={(fileId) => {
                    // Trigger mapping generation
                    console.log('Mapping requested for file:', fileId);
                  }}
                />
              </CardContent>
            </Card>
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* Panel 3: Field Mapping Visualization */}
          <ResizablePanel defaultSize={35} minSize={30} maxSize={45}>
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center text-lg">
                  <GitBranch className="h-5 w-5 mr-2 text-purple-500" />
                  Field Mappings
                  {(selectedFileId || activeMappingId) && (
                    <Badge variant="secondary" className="ml-2 text-xs">
                      {activeMappingId ? 'Mapping Loaded' : 'Ready to Map'}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="h-[calc(100%-80px)] overflow-hidden">
                <MappingPanel
                  fileId={selectedFileId}
                  mappingId={activeMappingId}
                  onMappingSelect={handleMappingSelect}
                  onMappingGenerate={(fileId) => {
                    console.log('Generate mapping for file:', fileId);
                  }}
                />
              </CardContent>
            </Card>
          </ResizablePanel>
        </ResizablePanelGroup>
      </main>

      {/* Footer Status Bar */}
      <footer className="border-t bg-card p-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center space-x-4">
            <span>SmithRx Claims Processing POC</span>
            <span>•</span>
            <span>Backend: localhost:8000</span>
          </div>
          
          <div className="flex items-center space-x-4">
            {selectedFileId && (
              <span className="text-blue-500">File: {selectedFileId.slice(0, 8)}...</span>
            )}
            {activeConversationId && (
              <span className="text-green-500">Chat: {activeConversationId.slice(0, 8)}...</span>
            )}
            {activeMappingId && (
              <span className="text-purple-500">Mapping: {activeMappingId.slice(0, 8)}...</span>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}