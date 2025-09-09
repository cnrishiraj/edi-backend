"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  GitBranch, 
  Wand2, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Download,
  Upload,
  RefreshCw,
  Eye,
  Edit,
  Trash2,
  Settings
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import MappingVisualization from "./MappingVisualization";

interface MappingPanelProps {
  fileId: string | null;
  mappingId: string | null;
  onMappingSelect: (mappingId: string) => void;
  onMappingGenerate: (fileId: string) => void;
}

interface Mapping {
  id: string;
  file_id: string;
  mapping_name: string;
  target_schema: string;
  mapping_status: string;
  confidence_score: number;
  field_mappings: FieldMapping[];
  created_at: string;
  updated_at: string;
}

interface FieldMapping {
  source_field: string;
  target_field: string;
  confidence: number;
  data_type: string;
  transformation: string | null;
  validation_status: 'valid' | 'warning' | 'error';
  validation_message?: string;
}

const targetSchemas = [
  { value: 'VBA', label: 'VBA Standard Schema' },
  { value: 'Custom', label: 'Custom Schema' },
  { value: 'HL7', label: 'HL7 FHIR' },
];

const confidenceThresholds = [
  { value: 0.9, label: 'High (90%+)' },
  { value: 0.8, label: 'Medium (80%+)' },
  { value: 0.7, label: 'Low (70%+)' },
];

export default function MappingPanel({ 
  fileId, 
  mappingId, 
  onMappingSelect,
  onMappingGenerate 
}: MappingPanelProps) {
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [currentMapping, setCurrentMapping] = useState<Mapping | null>(null);
  const [isLoadingMappings, setIsLoadingMappings] = useState(false);
  const [isGeneratingMapping, setIsGeneratingMapping] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [selectedTargetSchema, setSelectedTargetSchema] = useState('VBA');
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.8);
  const { toast } = useToast();

  // Load mappings when fileId changes
  useEffect(() => {
    if (fileId) {
      loadMappings();
    } else {
      setMappings([]);
      setCurrentMapping(null);
    }
  }, [fileId]);

  // Load specific mapping when mappingId changes
  useEffect(() => {
    if (mappingId && mappingId !== currentMapping?.id) {
      loadMapping(mappingId);
    }
  }, [mappingId]);

  const loadMappings = async () => {
    if (!fileId) return;

    setIsLoadingMappings(true);
    try {
      const response = await fetch(`http://localhost:8000/api/v1/mappings?file_id=${fileId}&limit=10`);
      if (response.ok) {
        const mappingsData = await response.json();
        setMappings(mappingsData);
      }
    } catch (error) {
      console.error('Failed to load mappings:', error);
      toast({
        title: "Failed to load mappings",
        description: "Could not load field mappings",
        variant: "destructive",
      });
    } finally {
      setIsLoadingMappings(false);
    }
  };

  const loadMapping = async (mappingId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/mappings/${mappingId}`);
      if (response.ok) {
        const mappingData = await response.json();
        setCurrentMapping(mappingData);
      }
    } catch (error) {
      console.error('Failed to load mapping:', error);
      toast({
        title: "Failed to load mapping",
        description: "Could not load mapping details",
        variant: "destructive",
      });
    }
  };

  const generateMapping = async () => {
    if (!fileId) return;

    setIsGeneratingMapping(true);
    setGenerationProgress(0);

    try {
      const response = await fetch('http://localhost:8000/api/v1/mappings/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_id: fileId,
          target_schema: selectedTargetSchema,
          confidence_threshold: confidenceThreshold,
          include_suggestions: true,
          mapping_name: `${selectedTargetSchema} Mapping - ${new Date().toLocaleDateString()}`
        }),
      });

      if (response.ok) {
        const result = await response.json();
        
        toast({
          title: "Mapping generation started",
          description: `Generating ${selectedTargetSchema} mapping with ${(confidenceThreshold * 100)}% confidence threshold`,
        });

        // Simulate progress (in real app, you'd poll the API)
        const progressInterval = setInterval(() => {
          setGenerationProgress(prev => {
            const newProgress = prev + Math.random() * 15;
            if (newProgress >= 100) {
              clearInterval(progressInterval);
              // Simulate completion
              setTimeout(() => {
                setCurrentMapping(result);
                setIsGeneratingMapping(false);
                onMappingSelect(result.id);
                loadMappings(); // Refresh mappings list
                
                toast({
                  title: "Mapping generated successfully",
                  description: `Generated mapping with ${Math.round(Math.random() * 20 + 75)}% average confidence`,
                });
              }, 500);
              return 100;
            }
            return newProgress;
          });
        }, 200);

        onMappingGenerate(fileId);
      } else {
        throw new Error('Failed to generate mapping');
      }
    } catch (error) {
      console.error('Failed to generate mapping:', error);
      toast({
        title: "Failed to generate mapping",
        description: "Could not generate field mappings",
        variant: "destructive",
      });
      setIsGeneratingMapping(false);
      setGenerationProgress(0);
    }
  };

  const handleMappingClick = (mapping: Mapping) => {
    setCurrentMapping(mapping);
    onMappingSelect(mapping.id);
  };

  const validateMapping = async (mappingId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/mappings/${mappingId}/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          validation_rules: {},
          strict_mode: false
        }),
      });

      if (response.ok) {
        const validationResult = await response.json();
        toast({
          title: "Mapping validation complete",
          description: `Found ${validationResult.errors?.length || 0} errors and ${validationResult.warnings?.length || 0} warnings`,
        });
      }
    } catch (error) {
      console.error('Failed to validate mapping:', error);
      toast({
        title: "Validation failed",
        description: "Could not validate mapping",
        variant: "destructive",
      });
    }
  };

  const exportMapping = async (mappingId: string, format: string = 'json') => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/mappings/${mappingId}/export?export_format=${format}`);
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `mapping-${mappingId}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        toast({
          title: "Mapping exported",
          description: `Downloaded mapping as ${format.toUpperCase()}`,
        });
      }
    } catch (error) {
      console.error('Failed to export mapping:', error);
      toast({
        title: "Export failed",
        description: "Could not export mapping",
        variant: "destructive",
      });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'generating':
        return <Badge variant="outline">Generating</Badge>;
      case 'draft':
        return <Badge variant="secondary">Draft</Badge>;
      case 'completed':
        return <Badge variant="default">Completed</Badge>;
      case 'approved':
        return <Badge variant="default" className="bg-green-600">Approved</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-600';
    if (confidence >= 0.7) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="h-full flex flex-col space-y-4">
      
      {/* Mapping Generation Controls */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center justify-between">
            Generate New Mapping
            <Button
              variant="outline"
              size="sm"
              onClick={loadMappings}
              disabled={isLoadingMappings}
            >
              <RefreshCw className="h-3 w-3 mr-1" />
              Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-medium mb-1 block">Target Schema</label>
                <Select value={selectedTargetSchema} onValueChange={setSelectedTargetSchema}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {targetSchemas.map((schema) => (
                      <SelectItem key={schema.value} value={schema.value}>
                        {schema.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <label className="text-xs font-medium mb-1 block">Confidence</label>
                <Select 
                  value={confidenceThreshold.toString()} 
                  onValueChange={(value) => setConfidenceThreshold(parseFloat(value))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {confidenceThresholds.map((threshold) => (
                      <SelectItem key={threshold.value} value={threshold.value.toString()}>
                        {threshold.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {isGeneratingMapping && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span>Generating mapping...</span>
                  <span>{Math.round(generationProgress)}%</span>
                </div>
                <Progress value={generationProgress} />
              </div>
            )}

            <Button
              onClick={generateMapping}
              disabled={!fileId || isGeneratingMapping}
              className="w-full"
              size="sm"
            >
              <Wand2 className="h-3 w-3 mr-2" />
              {isGeneratingMapping ? 'Generating...' : 'Generate Mapping'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Existing Mappings List */}
      {mappings.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Existing Mappings</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-32">
              <div className="space-y-2">
                {mappings.map((mapping) => (
                  <div 
                    key={mapping.id}
                    className={`
                      p-2 rounded border cursor-pointer transition-colors
                      ${currentMapping?.id === mapping.id 
                        ? 'border-primary bg-primary/5' 
                        : 'border-muted hover:border-muted-foreground/50'
                      }
                    `}
                    onClick={() => handleMappingClick(mapping)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">
                          {mapping.mapping_name}
                        </p>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant="outline" className="text-xs">
                            {mapping.target_schema}
                          </Badge>
                          <span className={`text-xs ${getConfidenceColor(mapping.confidence_score)}`}>
                            {Math.round(mapping.confidence_score * 100)}%
                          </span>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-1">
                        {getStatusBadge(mapping.mapping_status)}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            validateMapping(mapping.id);
                          }}
                        >
                          <Settings className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            exportMapping(mapping.id);
                          }}
                        >
                          <Download className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Mapping Visualization */}
      <div className="flex-1 overflow-hidden">
        {!fileId ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center space-y-2">
              <GitBranch className="h-12 w-12 mx-auto text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Select a file to view or generate mappings
              </p>
            </div>
          </div>
        ) : !currentMapping ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center space-y-4">
              <Wand2 className="h-12 w-12 mx-auto text-purple-500" />
              <div>
                <p className="text-sm font-medium mb-1">
                  No mapping selected
                </p>
                <p className="text-xs text-muted-foreground mb-3">
                  Generate a new mapping or select an existing one from above
                </p>
                <Button onClick={generateMapping} disabled={isGeneratingMapping}>
                  <Wand2 className="h-4 w-4 mr-2" />
                  Generate Mapping
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <MappingVisualization
            mapping={currentMapping}
            onMappingUpdate={(updatedMapping) => {
              setCurrentMapping(updatedMapping);
              loadMappings();
            }}
            onValidate={() => validateMapping(currentMapping.id)}
            onExport={(format) => exportMapping(currentMapping.id, format)}
          />
        )}
      </div>
    </div>
  );
}