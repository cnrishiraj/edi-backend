"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  FileText, 
  CheckCircle, 
  Clock, 
  XCircle, 
  AlertCircle,
  Download,
  Trash2,
  Eye,
  MoreVertical,
  Calendar,
  HardDrive
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useToast } from "@/hooks/use-toast";
import { formatDistanceToNow, format } from 'date-fns';

interface FileListProps {
  selectedFileId: string | null;
  onFileSelect: (fileId: string) => void;
  refreshTrigger: number; // Used to trigger refresh when files are uploaded
}

interface FileInfo {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  processing_status: string;
  upload_timestamp: string;
  record_count?: number;
  file_metadata?: {
    fields?: string[];
    encoding?: string;
    delimiter?: string;
  };
}

export default function FileList({ 
  selectedFileId, 
  onFileSelect,
  refreshTrigger 
}: FileListProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'size'>('date');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const { toast } = useToast();

  // Load files when component mounts or when refreshTrigger changes
  useEffect(() => {
    loadFiles();
  }, [refreshTrigger]);

  const loadFiles = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('limit', '50');
      if (filterStatus !== 'all') {
        params.append('status', filterStatus);
      }

      const response = await fetch(`http://localhost:8000/api/v1/files?${params}`);
      if (response.ok) {
        let filesData = await response.json();
        
        // Sort files
        filesData = filesData.sort((a: FileInfo, b: FileInfo) => {
          switch (sortBy) {
            case 'name':
              return a.filename.localeCompare(b.filename);
            case 'size':
              return b.file_size - a.file_size;
            case 'date':
            default:
              return new Date(b.upload_timestamp).getTime() - new Date(a.upload_timestamp).getTime();
          }
        });

        setFiles(filesData);
      }
    } catch (error) {
      console.error('Failed to load files:', error);
      toast({
        title: "Failed to load files",
        description: "Could not load file list",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const deleteFile = async (fileId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/v1/files/${fileId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        toast({
          title: "File deleted",
          description: `Successfully deleted ${filename}`,
        });

        // Refresh the file list
        loadFiles();

        // Clear selection if deleted file was selected
        if (selectedFileId === fileId) {
          onFileSelect('');
        }
      } else {
        throw new Error('Failed to delete file');
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      toast({
        title: "Delete failed",
        description: `Could not delete ${filename}`,
        variant: "destructive",
      });
    }
  };

  const downloadFile = async (fileId: string, filename: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/files/${fileId}/download`);
      
      if (response.ok) {
        const data = await response.json();
        
        // Create and trigger download
        const blob = new Blob([data.content], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        toast({
          title: "File downloaded",
          description: `Downloaded ${filename}`,
        });
      } else {
        throw new Error('Failed to download file');
      }
    } catch (error) {
      console.error('Failed to download file:', error);
      toast({
        title: "Download failed",
        description: `Could not download ${filename}`,
        variant: "destructive",
      });
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'uploading':
        return <Clock className="h-4 w-4 text-blue-500" />;
      case 'parsing':
        return <Clock className="h-4 w-4 text-yellow-500 animate-pulse" />;
      case 'parsed':
      case 'completed':
      case 'indexed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'uploading':
        return <Badge variant="outline">Uploading</Badge>;
      case 'parsing':
        return <Badge variant="outline">Processing</Badge>;
      case 'parsed':
        return <Badge variant="default">Parsed</Badge>;
      case 'completed':
        return <Badge variant="default">Completed</Badge>;
      case 'indexed':
        return <Badge variant="default" className="bg-blue-600">Indexed</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileTypeIcon = (fileType: string) => {
    // You could use different icons for different file types
    return <FileText className="h-4 w-4 text-blue-500" />;
  };

  const uniqueStatuses = [...new Set(files.map(f => f.processing_status))];

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-2">
          <Clock className="h-8 w-8 mx-auto text-muted-foreground animate-pulse" />
          <p className="text-sm text-muted-foreground">Loading files...</p>
        </div>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-2">
          <FileText className="h-12 w-12 mx-auto text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No files uploaded yet
          </p>
          <p className="text-xs text-muted-foreground">
            Drag and drop files above to get started
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      
      {/* File List Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <p className="text-sm font-medium">
            Files ({files.length})
          </p>
          
          {/* Status Filter */}
          <select 
            className="text-xs border rounded px-2 py-1"
            value={filterStatus}
            onChange={(e) => {
              setFilterStatus(e.target.value);
              loadFiles();
            }}
          >
            <option value="all">All Status</option>
            {uniqueStatuses.map(status => (
              <option key={status} value={status}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Sort Options */}
        <select
          className="text-xs border rounded px-2 py-1"
          value={sortBy}
          onChange={(e) => {
            setSortBy(e.target.value as 'date' | 'name' | 'size');
            loadFiles();
          }}
        >
          <option value="date">Sort by Date</option>
          <option value="name">Sort by Name</option>
          <option value="size">Sort by Size</option>
        </select>
      </div>

      {/* File List */}
      <ScrollArea className="flex-1">
        <div className="space-y-2">
          {files.map((file) => (
            <Card 
              key={file.id}
              className={`
                cursor-pointer transition-all hover:shadow-md
                ${selectedFileId === file.id 
                  ? 'border-primary shadow-sm' 
                  : 'hover:border-muted-foreground/50'
                }
              `}
              onClick={() => onFileSelect(file.id)}
            >
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  
                  {/* File Info */}
                  <div className="flex-1 min-w-0 mr-2">
                    <div className="flex items-center space-x-2 mb-1">
                      {getFileTypeIcon(file.file_type)}
                      <h4 className="text-sm font-medium truncate">
                        {file.filename}
                      </h4>
                    </div>
                    
                    <div className="flex items-center space-x-2 mb-2">
                      {getStatusIcon(file.processing_status)}
                      {getStatusBadge(file.processing_status)}
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                      <div className="flex items-center space-x-1">
                        <HardDrive className="h-3 w-3" />
                        <span>{formatFileSize(file.file_size)}</span>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        <Calendar className="h-3 w-3" />
                        <span title={format(new Date(file.upload_timestamp), 'PPpp')}>
                          {formatDistanceToNow(new Date(file.upload_timestamp), { addSuffix: true })}
                        </span>
                      </div>
                      
                      {file.record_count && (
                        <div className="col-span-2">
                          <span className="font-medium">{file.record_count.toLocaleString()}</span> records
                        </div>
                      )}
                      
                      {file.file_metadata?.fields && (
                        <div className="col-span-2">
                          <span className="font-medium">{file.file_metadata.fields.length}</span> fields
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Action Menu */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="sm">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation();
                        onFileSelect(file.id);
                      }}>
                        <Eye className="h-4 w-4 mr-2" />
                        View Details
                      </DropdownMenuItem>
                      
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation();
                        downloadFile(file.id, file.filename);
                      }}>
                        <Download className="h-4 w-4 mr-2" />
                        Download
                      </DropdownMenuItem>
                      
                      <DropdownMenuSeparator />
                      
                      <DropdownMenuItem 
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteFile(file.id, file.filename);
                        }}
                        className="text-red-600"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}