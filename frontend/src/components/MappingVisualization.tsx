"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  ArrowRight,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Edit,
  Save,
  X,
  Search,
  Filter,
  Download,
  CheckSquare,
  Square,
  Eye,
  EyeOff,
  Zap,
  Target
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface MappingVisualizationProps {
  mapping: {
    id: string;
    file_id: string;
    mapping_name: string;
    target_schema: string;
    mapping_status: string;
    confidence_score: number;
    field_mappings: FieldMapping[];
    created_at: string;
    updated_at: string;
  };
  onMappingUpdate: (updatedMapping: any) => void;
  onValidate: () => void;
  onExport: (format: string) => void;
}

interface FieldMapping {
  source_field: string;
  target_field: string;
  confidence: number;
  data_type: string;
  transformation?: string;
  validation_status: 'valid' | 'warning' | 'error';
  validation_message?: string;
}

const dataTypes = ['string', 'number', 'date', 'boolean', 'currency', 'email', 'phone'];
const transformations = ['none', 'uppercase', 'lowercase', 'trim', 'format_date', 'format_currency', 'custom'];

export default function MappingVisualization({ 
  mapping, 
  onMappingUpdate, 
  onValidate, 
  onExport 
}: MappingVisualizationProps) {
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>(mapping.field_mappings || []);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterConfidence, setFilterConfidence] = useState<string>('all');
  const [selectedFields, setSelectedFields] = useState<Set<string>>(new Set());
  const [showUnmapped, setShowUnmapped] = useState(true);
  const { toast } = useToast();

  // Update local state when mapping prop changes
  useEffect(() => {
    setFieldMappings(mapping.field_mappings || []);
  }, [mapping.field_mappings]);

  const filteredMappings = fieldMappings.filter(mapping => {
    // Search filter
    if (searchTerm && 
        !mapping.source_field.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !mapping.target_field.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }

    // Status filter
    if (filterStatus !== 'all' && mapping.validation_status !== filterStatus) {
      return false;
    }

    // Confidence filter
    if (filterConfidence !== 'all') {
      const confidence = mapping.confidence;
      switch (filterConfidence) {
        case 'high':
          if (confidence < 0.9) return false;
          break;
        case 'medium':
          if (confidence < 0.7 || confidence >= 0.9) return false;
          break;
        case 'low':
          if (confidence >= 0.7) return false;
          break;
      }
    }

    // Unmapped filter
    if (!showUnmapped && !mapping.target_field) {
      return false;
    }

    return true;
  });

  const updateFieldMapping = async (sourceField: string, updates: Partial<FieldMapping>) => {
    try {
      const updatedMappings = fieldMappings.map(mapping =>
        mapping.source_field === sourceField
          ? { ...mapping, ...updates }
          : mapping
      );

      setFieldMappings(updatedMappings);

      // Update via API
      const response = await fetch(`http://localhost:8000/api/v1/mappings/${mapping.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          field_mappings: updatedMappings
        }),
      });

      if (response.ok) {
        const updatedMapping = await response.json();
        onMappingUpdate(updatedMapping);
        
        toast({
          title: "Mapping updated",
          description: `Updated mapping for ${sourceField}`,
        });
      } else {
        throw new Error('Failed to update mapping');
      }
    } catch (error) {
      console.error('Failed to update field mapping:', error);
      toast({
        title: "Update failed",
        description: "Could not update field mapping",
        variant: "destructive",
      });
    }
  };

  const handleBulkAction = async (action: 'approve' | 'reject' | 'auto_map') => {
    const selectedMappings = fieldMappings.filter(fm => selectedFields.has(fm.source_field));
    
    if (selectedMappings.length === 0) {
      toast({
        title: "No fields selected",
        description: "Please select fields to perform bulk actions",
        variant: "destructive",
      });
      return;
    }

    try {
      let updates: Partial<FieldMapping> = {};
      
      switch (action) {
        case 'approve':
          updates = { validation_status: 'valid' };
          break;
        case 'reject':
          updates = { validation_status: 'error', validation_message: 'Manually rejected' };
          break;
        case 'auto_map':
          // This would trigger AI re-mapping
          toast({
            title: "Auto-mapping started",
            description: `Re-mapping ${selectedMappings.length} fields with AI`,
          });
          break;
      }

      if (action !== 'auto_map') {
        const updatedMappings = fieldMappings.map(mapping =>
          selectedFields.has(mapping.source_field)
            ? { ...mapping, ...updates }
            : mapping
        );

        setFieldMappings(updatedMappings);
        
        const response = await fetch(`http://localhost:8000/api/v1/mappings/${mapping.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            field_mappings: updatedMappings
          }),
        });

        if (response.ok) {
          const updatedMapping = await response.json();
          onMappingUpdate(updatedMapping);
          setSelectedFields(new Set());
          
          toast({
            title: "Bulk action completed",
            description: `Updated ${selectedMappings.length} field mappings`,
          });
        }
      }
    } catch (error) {
      console.error('Failed to perform bulk action:', error);
      toast({
        title: "Bulk action failed",
        description: "Could not perform bulk action",
        variant: "destructive",
      });
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-600';
    if (confidence >= 0.7) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getConfidenceBackground = (confidence: number) => {
    if (confidence >= 0.9) return 'bg-green-50 border-green-200';
    if (confidence >= 0.7) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'valid':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-gray-500" />;
    }
  };

  const toggleFieldSelection = (sourceField: string) => {
    const newSelection = new Set(selectedFields);
    if (newSelection.has(sourceField)) {
      newSelection.delete(sourceField);
    } else {
      newSelection.add(sourceField);
    }
    setSelectedFields(newSelection);
  };

  const toggleAllFields = () => {
    if (selectedFields.size === filteredMappings.length) {
      setSelectedFields(new Set());
    } else {
      setSelectedFields(new Set(filteredMappings.map(fm => fm.source_field)));
    }
  };

  const validMappings = fieldMappings.filter(fm => fm.validation_status === 'valid').length;
  const warningMappings = fieldMappings.filter(fm => fm.validation_status === 'warning').length;
  const errorMappings = fieldMappings.filter(fm => fm.validation_status === 'error').length;
  const avgConfidence = fieldMappings.reduce((sum, fm) => sum + fm.confidence, 0) / fieldMappings.length;

  return (
    <div className="h-full flex flex-col space-y-4">
      
      {/* Mapping Summary */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">{mapping.mapping_name}</CardTitle>
            <div className="flex items-center space-x-2">
              <Badge variant="outline">{mapping.target_schema}</Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={onValidate}
              >
                <CheckCircle className="h-3 w-3 mr-1" />
                Validate
              </Button>
              <Select onValueChange={onExport}>
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="Export" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="json">Export JSON</SelectItem>
                  <SelectItem value="csv">Export CSV</SelectItem>
                  <SelectItem value="excel">Export Excel</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-green-600">{validMappings}</p>
              <p className="text-xs text-muted-foreground">Valid</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-yellow-600">{warningMappings}</p>
              <p className="text-xs text-muted-foreground">Warnings</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{errorMappings}</p>
              <p className="text-xs text-muted-foreground">Errors</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">{Math.round(avgConfidence * 100)}%</p>
              <p className="text-xs text-muted-foreground">Avg Confidence</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters and Bulk Actions */}
      <Card>
        <CardContent className="p-3">
          <div className="flex items-center justify-between">
            
            {/* Search and Filters */}
            <div className="flex items-center space-x-2">
              <div className="relative">
                <Search className="h-4 w-4 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search fields..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8 w-48"
                />
              </div>
              
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="valid">Valid</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>

              <Select value={filterConfidence} onValueChange={setFilterConfidence}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Confidence</SelectItem>
                  <SelectItem value="high">High (90%+)</SelectItem>
                  <SelectItem value="medium">Medium (70-90%)</SelectItem>
                  <SelectItem value="low">Low (&lt;70%)</SelectItem>
                </SelectContent>
              </Select>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUnmapped(!showUnmapped)}
              >
                {showUnmapped ? <EyeOff className="h-3 w-3 mr-1" /> : <Eye className="h-3 w-3 mr-1" />}
                {showUnmapped ? 'Hide' : 'Show'} Unmapped
              </Button>
            </div>

            {/* Bulk Actions */}
            {selectedFields.size > 0 && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-muted-foreground">
                  {selectedFields.size} selected
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkAction('approve')}
                >
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Approve
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkAction('reject')}
                >
                  <XCircle className="h-3 w-3 mr-1" />
                  Reject
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkAction('auto_map')}
                >
                  <Zap className="h-3 w-3 mr-1" />
                  Auto-Map
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Field Mappings List */}
      <div className="flex-1 overflow-hidden">
        <Card className="h-full">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">
                Field Mappings ({filteredMappings.length})
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleAllFields}
              >
                {selectedFields.size === filteredMappings.length ? (
                  <CheckSquare className="h-4 w-4" />
                ) : (
                  <Square className="h-4 w-4" />
                )}
              </Button>
            </div>
          </CardHeader>
          
          <CardContent className="h-[calc(100%-80px)] p-0">
            <ScrollArea className="h-full">
              <div className="p-3 space-y-2">
                {filteredMappings.map((fieldMapping) => (
                  <Card 
                    key={fieldMapping.source_field}
                    className={`
                      ${getConfidenceBackground(fieldMapping.confidence)}
                      transition-all hover:shadow-sm
                      ${selectedFields.has(fieldMapping.source_field) 
                        ? 'ring-2 ring-primary' 
                        : ''
                      }
                    `}
                  >
                    <CardContent className="p-3">
                      <div className="flex items-start space-x-3">
                        
                        {/* Selection Checkbox */}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="p-0 h-auto"
                          onClick={() => toggleFieldSelection(fieldMapping.source_field)}
                        >
                          {selectedFields.has(fieldMapping.source_field) ? (
                            <CheckSquare className="h-4 w-4 text-primary" />
                          ) : (
                            <Square className="h-4 w-4" />
                          )}
                        </Button>

                        {/* Mapping Visualization */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2 mb-2">
                            
                            {/* Source Field */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center space-x-1">
                                <Badge variant="outline" className="text-xs">
                                  {fieldMapping.data_type}
                                </Badge>
                                <span className="text-sm font-medium truncate">
                                  {fieldMapping.source_field}
                                </span>
                              </div>
                            </div>

                            {/* Arrow */}
                            <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />

                            {/* Target Field */}
                            <div className="flex-1 min-w-0">
                              {editingField === fieldMapping.source_field ? (
                                <div className="flex items-center space-x-1">
                                  <Input
                                    value={fieldMapping.target_field}
                                    onChange={(e) => {
                                      const updated = fieldMappings.map(fm =>
                                        fm.source_field === fieldMapping.source_field
                                          ? { ...fm, target_field: e.target.value }
                                          : fm
                                      );
                                      setFieldMappings(updated);
                                    }}
                                    className="h-6 text-xs"
                                    placeholder="Enter target field..."
                                  />
                                  <Button
                                    size="sm"
                                    onClick={() => {
                                      updateFieldMapping(fieldMapping.source_field, {
                                        target_field: fieldMapping.target_field
                                      });
                                      setEditingField(null);
                                    }}
                                  >
                                    <Save className="h-3 w-3" />
                                  </Button>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setEditingField(null)}
                                  >
                                    <X className="h-3 w-3" />
                                  </Button>
                                </div>
                              ) : (
                                <div className="flex items-center space-x-1">
                                  <Badge variant="secondary" className="text-xs">
                                    <Target className="h-3 w-3 mr-1" />
                                    VBA
                                  </Badge>
                                  <span className="text-sm truncate">
                                    {fieldMapping.target_field || 'No mapping'}
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setEditingField(fieldMapping.source_field)}
                                  >
                                    <Edit className="h-3 w-3" />
                                  </Button>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Confidence and Status */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              {getStatusIcon(fieldMapping.validation_status)}
                              <span className={`text-xs font-medium ${getConfidenceColor(fieldMapping.confidence)}`}>
                                {Math.round(fieldMapping.confidence * 100)}% confident
                              </span>
                              <Progress 
                                value={fieldMapping.confidence * 100} 
                                className="w-16 h-1" 
                              />
                            </div>

                            {fieldMapping.transformation && fieldMapping.transformation !== 'none' && (
                              <Badge variant="outline" className="text-xs">
                                Transform: {fieldMapping.transformation}
                              </Badge>
                            )}
                          </div>

                          {/* Validation Message */}
                          {fieldMapping.validation_message && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {fieldMapping.validation_message}
                            </p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}

                {filteredMappings.length === 0 && (
                  <div className="text-center py-8">
                    <Search className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No field mappings match your filters
                    </p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}