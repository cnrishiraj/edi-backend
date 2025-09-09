"use client";

import { useState, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertCircle,
  Trash2,
  Download,
  Eye
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import FileList from "./FileList";

interface FileUploadPanelProps {
  selectedFileId: string | null;
  onFileSelect: (fileId: string) => void;
  onFileProcessed: (fileId: string) => void;
}

interface UploadingFile {
  id: string;
  file: File;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}

export default function FileUploadPanel({ 
  selectedFileId, 
  onFileSelect, 
  onFileProcessed 
}: FileUploadPanelProps) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      handleFiles(files);
    }
  }, []);

  const handleFiles = async (files: File[]) => {
    const validExtensions = ['.csv', '.txt', '.xlsx', '.xls'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    for (const file of files) {
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
      
      // Validate file type
      if (!validExtensions.includes(fileExtension)) {
        toast({
          title: "Invalid file type",
          description: `${file.name} is not a supported file type. Please use: ${validExtensions.join(', ')}`,
          variant: "destructive",
        });
        continue;
      }

      // Validate file size
      if (file.size > maxSize) {
        toast({
          title: "File too large",
          description: `${file.name} exceeds the 10MB limit.`,
          variant: "destructive",
        });
        continue;
      }

      // Add to uploading files
      const uploadingFile: UploadingFile = {
        id: Math.random().toString(36).substr(2, 9),
        file,
        progress: 0,
        status: 'uploading'
      };

      setUploadingFiles(prev => [...prev, uploadingFile]);
      
      // Start upload
      await uploadFile(uploadingFile);
    }
  };

  const uploadFile = async (uploadingFile: UploadingFile) => {
    try {
      const formData = new FormData();
      formData.append('file', uploadingFile.file);

      // Create XMLHttpRequest for progress tracking
      const xhr = new XMLHttpRequest();
      
      // Track upload progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const progress = Math.round((e.loaded * 100) / e.total);
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFile.id 
                ? { ...f, progress } 
                : f
            )
          );
        }
      });

      // Handle completion
      xhr.addEventListener('load', async () => {
        if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText);
          
          // Update to processing status
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFile.id 
                ? { ...f, status: 'processing', progress: 100 } 
                : f
            )
          );

          // Poll for processing completion
          await pollFileStatus(response.id, uploadingFile.id);
          
        } else {
          // Handle error
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFile.id 
                ? { ...f, status: 'failed', error: `Upload failed: ${xhr.statusText}` } 
                : f
            )
          );
          
          toast({
            title: "Upload failed",
            description: `Failed to upload ${uploadingFile.file.name}`,
            variant: "destructive",
          });
        }
      });

      // Handle network errors
      xhr.addEventListener('error', () => {
        setUploadingFiles(prev => 
          prev.map(f => 
            f.id === uploadingFile.id 
              ? { ...f, status: 'failed', error: 'Network error' } 
              : f
          )
        );
        
        toast({
          title: "Network error",
          description: `Failed to upload ${uploadingFile.file.name}`,
          variant: "destructive",
        });
      });

      // Start the upload
      xhr.open('POST', 'http://localhost:8000/api/v1/files/upload');
      xhr.send(formData);

    } catch (error) {
      setUploadingFiles(prev => 
        prev.map(f => 
          f.id === uploadingFile.id 
            ? { ...f, status: 'failed', error: error instanceof Error ? error.message : 'Unknown error' } 
            : f
        )
      );
      
      toast({
        title: "Upload error",
        description: `Error uploading ${uploadingFile.file.name}`,
        variant: "destructive",
      });
    }
  };

  const pollFileStatus = async (fileId: string, uploadingFileId: string) => {
    const maxAttempts = 30; // 30 attempts = ~60 seconds
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/v1/files/${fileId}/status`);
        const fileData = await response.json();

        if (fileData.processing_status === 'completed' || fileData.processing_status === 'parsed') {
          // File processing completed
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFileId 
                ? { ...f, status: 'completed' } 
                : f
            )
          );

          toast({
            title: "File processed successfully",
            description: `${fileData.filename} is ready for analysis`,
          });

          onFileProcessed(fileId);
          
          // Remove from uploading files after a delay
          setTimeout(() => {
            setUploadingFiles(prev => prev.filter(f => f.id !== uploadingFileId));
          }, 3000);

        } else if (fileData.processing_status === 'failed') {
          // Processing failed
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFileId 
                ? { ...f, status: 'failed', error: 'Processing failed' } 
                : f
            )
          );

          toast({
            title: "Processing failed",
            description: `Failed to process ${fileData.filename}`,
            variant: "destructive",
          });

        } else if (attempts < maxAttempts) {
          // Still processing, continue polling
          attempts++;
          setTimeout(poll, 2000);
        } else {
          // Timeout
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFileId 
                ? { ...f, status: 'failed', error: 'Processing timeout' } 
                : f
            )
          );
        }

      } catch (error) {
        if (attempts < maxAttempts) {
          attempts++;
          setTimeout(poll, 2000);
        } else {
          setUploadingFiles(prev => 
            prev.map(f => 
              f.id === uploadingFileId 
                ? { ...f, status: 'failed', error: 'Status check failed' } 
                : f
            )
          );
        }
      }
    };

    poll();
  };

  const removeUploadingFile = (id: string) => {
    setUploadingFiles(prev => prev.filter(f => f.id !== id));
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return <Clock className="h-4 w-4 text-blue-500" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'uploading':
        return <Badge variant="outline">Uploading</Badge>;
      case 'processing':
        return <Badge variant="outline">Processing</Badge>;
      case 'completed':
        return <Badge variant="default">Completed</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
  };

  return (
    <div className="h-full flex flex-col space-y-4">
      
      {/* Upload Area */}
      <div
        className={`
          border-2 border-dashed rounded-lg p-6 text-center transition-colors
          ${isDragOver 
            ? 'border-primary bg-primary/5' 
            : 'border-muted-foreground/25 hover:border-muted-foreground/50'
          }
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
        <p className="text-sm font-medium mb-1">
          Drop SmithRx files here or click to browse
        </p>
        <p className="text-xs text-muted-foreground mb-3">
          Supports CSV, TXT, Excel files (max 10MB)
        </p>
        <Button 
          variant="outline" 
          size="sm"
          onClick={() => fileInputRef.current?.click()}
        >
          Select Files
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".csv,.txt,.xlsx,.xls"
          onChange={handleFileInput}
          className="hidden"
        />
      </div>

      {/* Currently Uploading Files */}
      {uploadingFiles.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Uploading Files</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {uploadingFiles.map((uploadingFile) => (
                <div key={uploadingFile.id} className="flex items-center space-x-2">
                  {getStatusIcon(uploadingFile.status)}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">
                      {uploadingFile.file.name}
                    </p>
                    {uploadingFile.status === 'uploading' && (
                      <Progress value={uploadingFile.progress} className="h-1 mt-1" />
                    )}
                    {uploadingFile.status === 'processing' && (
                      <div className="flex items-center mt-1">
                        <div className="h-1 bg-primary/20 rounded-full flex-1">
                          <div className="h-1 bg-primary rounded-full animate-pulse" style={{width: '70%'}} />
                        </div>
                      </div>
                    )}
                    {uploadingFile.error && (
                      <p className="text-xs text-red-500 mt-1">{uploadingFile.error}</p>
                    )}
                  </div>
                  <div className="flex items-center space-x-1">
                    {getStatusBadge(uploadingFile.status)}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeUploadingFile(uploadingFile.id)}
                    >
                      <XCircle className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* File List */}
      <div className="flex-1 overflow-hidden">
        <FileList
          selectedFileId={selectedFileId}
          onFileSelect={onFileSelect}
          refreshTrigger={uploadingFiles.filter(f => f.status === 'completed').length}
        />
      </div>
    </div>
  );
}