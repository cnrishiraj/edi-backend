"""
Mapping engine for automatic field mapping generation with fuzzy matching
Generates mappings between EDI source fields and target schemas
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from difflib import SequenceMatcher
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MappingCandidate:
    """Represents a potential field mapping with confidence score"""
    source_field: str
    target_field: str
    confidence_score: float
    match_reasons: List[str]
    transformation_rules: List[Dict[str, Any]]
    sample_values: List[str]
    data_type: str


class VBAStandardSchema:
    """VBA Standard schema definition for healthcare claims"""
    
    SCHEMA_FIELDS = {
        # Core identifiers
        'claim_number': {
            'data_type': 'string',
            'required': True,
            'description': 'Unique claim identifier',
            'patterns': [r'^CLM\d+', r'^\d{8,12}$'],
            'max_length': 50
        },
        'member_id': {
            'data_type': 'string', 
            'required': True,
            'description': 'Member/patient identifier',
            'patterns': [r'^M\d+', r'^\d{9,12}$'],
            'max_length': 20
        },
        'provider_id': {
            'data_type': 'string',
            'required': True,
            'description': 'Healthcare provider identifier',
            'patterns': [r'^PRV\d+', r'^\d{6,10}$'],
            'max_length': 20
        },
        
        # Financial fields
        'claim_amount': {
            'data_type': 'decimal',
            'required': True,
            'description': 'Total claim amount',
            'min_value': 0.01,
            'max_value': 999999.99
        },
        'copay_amount': {
            'data_type': 'decimal',
            'required': False,
            'description': 'Patient copay amount',
            'min_value': 0.0,
            'max_value': 10000.0
        },
        'deductible_amount': {
            'data_type': 'decimal',
            'required': False,
            'description': 'Deductible amount applied',
            'min_value': 0.0,
            'max_value': 50000.0
        },
        'paid_amount': {
            'data_type': 'decimal',
            'required': False,
            'description': 'Amount actually paid',
            'min_value': 0.0
        },
        
        # Date fields
        'service_date': {
            'data_type': 'date',
            'required': True,
            'description': 'Date of service',
        },
        'received_date': {
            'data_type': 'date',
            'required': False,
            'description': 'Date claim was received',
        },
        'processed_date': {
            'data_type': 'date',
            'required': False,
            'description': 'Date claim was processed',
        },
        
        # Medical codes
        'diagnosis_code': {
            'data_type': 'string',
            'required': False,
            'description': 'Primary diagnosis code (ICD-10)',
            'patterns': [r'^[A-Z]\d{2}\.?\d{0,2}$'],
            'max_length': 10
        },
        'procedure_code': {
            'data_type': 'string', 
            'required': False,
            'description': 'Procedure code (CPT)',
            'patterns': [r'^\d{5}$'],
            'max_length': 10
        },
        'drug_code': {
            'data_type': 'string',
            'required': False,
            'description': 'Drug/medication code (NDC)',
            'patterns': [r'^\d{5}-\d{4}-\d{2}$', r'^NDC\d+$'],
            'max_length': 20
        },
        
        # Status and processing
        'claim_status': {
            'data_type': 'string',
            'required': True,
            'description': 'Current claim status',
            'allowed_values': ['APPROVED', 'PENDING', 'REJECTED', 'CANCELLED'],
            'max_length': 20
        },
        'rejection_reason': {
            'data_type': 'string',
            'required': False,
            'description': 'Reason for rejection if applicable',
            'max_length': 200
        },
        
        # Additional fields
        'line_number': {
            'data_type': 'integer',
            'required': False,
            'description': 'Line item number within claim',
            'min_value': 1,
            'max_value': 999
        },
        'units': {
            'data_type': 'integer',
            'required': False,
            'description': 'Number of units/services',
            'min_value': 1,
            'max_value': 9999
        }
    }


class MappingEngine:
    """Main mapping engine for automatic field mapping generation"""
    
    def __init__(self, target_schema: str = "vba_standard"):
        """
        Initialize the mapping engine
        
        Args:
            target_schema: Target schema to map to ('vba_standard' or 'custom')
        """
        self.target_schema = target_schema
        self.schema_fields = VBAStandardSchema.SCHEMA_FIELDS if target_schema == "vba_standard" else {}
        
        # Field name similarity patterns
        self.field_name_mappings = {
            # Claim identifiers
            'claim_number': ['claim_id', 'claimid', 'claim_no', 'clmno', 'claim_number', 'claim_ref'],
            'member_id': ['member_id', 'memberid', 'mbr_id', 'mbrid', 'patient_id', 'member_number'],
            'provider_id': ['provider_id', 'providerid', 'prv_id', 'prvid', 'provider_number', 'provider_code'],
            
            # Financial fields
            'claim_amount': ['amount', 'claim_amount', 'claimamount', 'total_amount', 'amt', 'claim_amt'],
            'copay_amount': ['copay', 'copay_amount', 'copayamt', 'copay_amt', 'coinsurance', 'patient_pay'],
            'deductible_amount': ['deductible', 'deductible_amount', 'deduct', 'deduct_amt', 'ded_amt'],
            'paid_amount': ['paid', 'paid_amount', 'paidamt', 'amount_paid', 'paid_amt'],
            
            # Date fields
            'service_date': ['service_date', 'servicedate', 'svc_date', 'svcdt', 'date_of_service', 'dos'],
            'received_date': ['received_date', 'receiveddate', 'recv_date', 'date_received'],
            'processed_date': ['processed_date', 'processdate', 'proc_date', 'process_dt'],
            
            # Medical codes
            'diagnosis_code': ['diagnosis_code', 'diagcode', 'diag_code', 'icd_code', 'dx_code', 'diagnosis'],
            'procedure_code': ['procedure_code', 'proccode', 'proc_code', 'cpt_code', 'procedure'],
            'drug_code': ['drug_code', 'drugcode', 'ndc_code', 'ndc', 'medication_code', 'med_code'],
            
            # Status fields
            'claim_status': ['status', 'claim_status', 'sts', 'processing_status', 'claim_sts'],
            'rejection_reason': ['rejection_code', 'reject_code', 'deny_code', 'error_code', 'reject_reason'],
            
            # Other fields
            'line_number': ['line_number', 'lineno', 'line_no', 'item_no', 'seq_no'],
            'units': ['units', 'quantity', 'qty', 'unit_count', 'service_units']
        }
        
        # Data type indicators
        self.data_type_indicators = {
            'date': ['date', 'dt', 'time', 'timestamp'],
            'decimal': ['amount', 'amt', 'cost', 'price', 'total', 'pay', 'ded'],
            'integer': ['count', 'number', 'no', 'qty', 'units', 'line'],
            'string': ['name', 'desc', 'code', 'id', 'status', 'reason']
        }
    
    def generate_mappings(self, 
                          source_fields: Dict[str, Dict[str, Any]],
                          parsed_data: pd.DataFrame,
                          confidence_threshold: float = 0.7,
                          use_excel_definitions: bool = False,
                          custom_rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate field mappings from source to target schema
        
        Args:
            source_fields: Source field definitions from file parser
            parsed_data: Parsed data for analysis
            confidence_threshold: Minimum confidence for auto-mapping
            use_excel_definitions: Whether to use Excel field definitions
            custom_rules: Custom mapping rules
        
        Returns:
            Dictionary with mapping results
        """
        try:
            logger.info(f"Generating mappings for {len(source_fields)} source fields")
            start_time = datetime.now()
            
            mapping_candidates = []
            unmapped_fields = []
            validation_results = []
            
            # Generate mapping candidates for each source field
            for source_field_name, source_field_def in source_fields.items():
                candidates = self._find_mapping_candidates(
                    source_field_name, 
                    source_field_def, 
                    parsed_data
                )
                
                best_candidate = None
                if candidates:
                    # Sort by confidence score and take the best
                    candidates.sort(key=lambda x: x.confidence_score, reverse=True)
                    best_candidate = candidates[0]
                
                if best_candidate and best_candidate.confidence_score >= confidence_threshold:
                    mapping_candidates.append(best_candidate)
                else:
                    unmapped_fields.append({
                        'field_name': source_field_name,
                        'data_type': source_field_def.get('data_type', 'unknown'),
                        'sample_values': source_field_def.get('sample_values', [])[:3],
                        'reason': 'Low confidence' if best_candidate else 'No suitable target found',
                        'suggested_mappings': [
                            {
                                'target_field': c.target_field,
                                'confidence': c.confidence_score,
                                'reasons': c.match_reasons
                            } for c in candidates[:3]
                        ] if candidates else []
                    })
            
            # Apply custom rules if provided
            if custom_rules:
                mapping_candidates = self._apply_custom_rules(mapping_candidates, custom_rules)
            
            # Validate mappings with sample data
            if parsed_data is not None and not parsed_data.empty:
                validation_results = self._validate_mappings_with_data(
                    mapping_candidates, 
                    parsed_data
                )
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(mapping_candidates)
            
            # Determine if manual review is required
            manual_review_required = (
                len(unmapped_fields) > 0 or 
                overall_confidence < 0.8 or
                any(mc.confidence_score < 0.9 for mc in mapping_candidates)
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'success': True,
                'field_mappings': [self._candidate_to_dict(mc) for mc in mapping_candidates],
                'unmapped_fields': unmapped_fields,
                'overall_confidence': overall_confidence,
                'manual_review_required': manual_review_required,
                'validation_results': {
                    'total_records_validated': len(parsed_data) if parsed_data is not None else 0,
                    'validation_errors': validation_results,
                    'data_quality_score': self._calculate_data_quality_score(validation_results, len(mapping_candidates))
                },
                'processing_time_seconds': processing_time,
                'target_schema': self.target_schema,
                'confidence_threshold': confidence_threshold,
                'custom_rules_applied': len(custom_rules) if custom_rules else 0
            }
            
            logger.info(f"Generated {len(mapping_candidates)} mappings in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate mappings: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'field_mappings': [],
                'unmapped_fields': [],
                'overall_confidence': 0.0
            }
    
    def _find_mapping_candidates(self, 
                                 source_field_name: str,
                                 source_field_def: Dict[str, Any],
                                 parsed_data: pd.DataFrame) -> List[MappingCandidate]:
        """Find potential mapping candidates for a source field"""
        candidates = []
        
        for target_field, target_def in self.schema_fields.items():
            confidence_score, match_reasons = self._calculate_field_similarity(
                source_field_name,
                source_field_def,
                target_field,
                target_def,
                parsed_data
            )
            
            if confidence_score > 0.3:  # Only consider reasonable matches
                # Generate transformation rules
                transformation_rules = self._generate_transformation_rules(
                    source_field_def,
                    target_def,
                    parsed_data,
                    source_field_name
                )
                
                candidate = MappingCandidate(
                    source_field=source_field_name,
                    target_field=target_field,
                    confidence_score=confidence_score,
                    match_reasons=match_reasons,
                    transformation_rules=transformation_rules,
                    sample_values=source_field_def.get('sample_values', [])[:5],
                    data_type=target_def['data_type']
                )
                
                candidates.append(candidate)
        
        return candidates
    
    def _calculate_field_similarity(self, 
                                    source_field: str,
                                    source_def: Dict[str, Any],
                                    target_field: str,
                                    target_def: Dict[str, Any],
                                    parsed_data: pd.DataFrame) -> Tuple[float, List[str]]:
        """Calculate similarity score between source and target fields"""
        confidence_factors = []
        match_reasons = []
        total_confidence = 0.0
        
        source_field_lower = source_field.lower()
        target_field_lower = target_field.lower()
        
        # 1. Exact name match (highest confidence)
        if source_field_lower == target_field_lower:
            total_confidence += 0.95
            match_reasons.append("Exact field name match")
            
        # 2. Check predefined mappings (high confidence)
        elif target_field in self.field_name_mappings:
            variations = [v.lower() for v in self.field_name_mappings[target_field]]
            if source_field_lower in variations:
                total_confidence += 0.9
                match_reasons.append("Predefined field mapping")
        
        # 3. Fuzzy string matching
        string_similarity = SequenceMatcher(None, source_field_lower, target_field_lower).ratio()
        if string_similarity > 0.6:
            confidence_boost = string_similarity * 0.7
            total_confidence += confidence_boost
            match_reasons.append(f"String similarity ({string_similarity:.2f})")
        
        # 4. Data type compatibility
        source_data_type = source_def.get('data_type', 'unknown')
        target_data_type = target_def.get('data_type', 'unknown')
        
        if source_data_type == target_data_type:
            total_confidence += 0.3
            match_reasons.append("Data type match")
        elif self._are_data_types_compatible(source_data_type, target_data_type):
            total_confidence += 0.2
            match_reasons.append("Compatible data types")
        else:
            total_confidence -= 0.2
            match_reasons.append("Data type mismatch")
        
        # 5. Pattern matching in field names
        pattern_score = self._check_field_patterns(source_field_lower, target_field_lower)
        if pattern_score > 0:
            total_confidence += pattern_score * 0.4
            match_reasons.append(f"Pattern similarity ({pattern_score:.2f})")
        
        # 6. Sample data validation (if available)
        if parsed_data is not None and source_field in parsed_data.columns:
            data_validation_score = self._validate_sample_data(
                parsed_data[source_field],
                target_def
            )
            total_confidence += data_validation_score * 0.3
            if data_validation_score > 0.5:
                match_reasons.append("Sample data validates")
        
        # 7. Semantic similarity based on keywords
        semantic_score = self._calculate_semantic_similarity(source_field_lower, target_field_lower)
        if semantic_score > 0.3:
            total_confidence += semantic_score * 0.25
            match_reasons.append(f"Semantic similarity ({semantic_score:.2f})")
        
        # Normalize confidence score to 0-1 range
        final_confidence = min(1.0, max(0.0, total_confidence))
        
        return final_confidence, match_reasons
    
    def _are_data_types_compatible(self, source_type: str, target_type: str) -> bool:
        """Check if two data types are compatible for mapping"""
        compatibility_map = {
            'string': ['string'],
            'integer': ['integer', 'decimal'],
            'decimal': ['decimal', 'integer'],
            'date': ['date', 'string'],
            'boolean': ['boolean', 'string', 'integer']
        }
        
        return target_type in compatibility_map.get(source_type, [])
    
    def _check_field_patterns(self, source_field: str, target_field: str) -> float:
        """Check for common patterns between field names"""
        # Split field names into components
        source_parts = re.split(r'[_\-\s]+', source_field)
        target_parts = re.split(r'[_\-\s]+', target_field)
        
        # Count matching parts
        matching_parts = 0
        for s_part in source_parts:
            for t_part in target_parts:
                if s_part == t_part or (len(s_part) > 2 and s_part in t_part) or (len(t_part) > 2 and t_part in s_part):
                    matching_parts += 1
                    break
        
        # Return score based on proportion of matching parts
        total_parts = max(len(source_parts), len(target_parts))
        return matching_parts / total_parts if total_parts > 0 else 0.0
    
    def _validate_sample_data(self, data_series: pd.Series, target_def: Dict[str, Any]) -> float:
        """Validate sample data against target field definition"""
        if data_series.empty:
            return 0.0
        
        sample_data = data_series.dropna().head(100)  # Use first 100 non-null values
        if sample_data.empty:
            return 0.0
        
        validation_score = 0.0
        total_checks = 0
        
        target_type = target_def.get('data_type')
        
        # Check data type compatibility
        if target_type == 'decimal':
            try:
                numeric_values = pd.to_numeric(sample_data.astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce')
                valid_numeric = numeric_values.notna().sum()
                validation_score += (valid_numeric / len(sample_data)) * 0.4
                total_checks += 1
                
                # Check value ranges if specified
                if 'min_value' in target_def and valid_numeric > 0:
                    in_range = (numeric_values >= target_def['min_value']).sum()
                    validation_score += (in_range / valid_numeric) * 0.2
                    total_checks += 1
                    
            except:
                pass
        
        elif target_type == 'date':
            date_like_count = sum(1 for val in sample_data if self._looks_like_date(str(val)))
            validation_score += (date_like_count / len(sample_data)) * 0.4
            total_checks += 1
        
        elif target_type == 'string':
            # Check allowed values if specified
            if 'allowed_values' in target_def:
                allowed_values = set(v.upper() for v in target_def['allowed_values'])
                matching_values = sum(1 for val in sample_data if str(val).upper() in allowed_values)
                validation_score += (matching_values / len(sample_data)) * 0.4
                total_checks += 1
            
            # Check max length if specified
            if 'max_length' in target_def:
                within_length = sum(1 for val in sample_data if len(str(val)) <= target_def['max_length'])
                validation_score += (within_length / len(sample_data)) * 0.2
                total_checks += 1
        
        # Check patterns if specified
        if 'patterns' in target_def:
            pattern_matches = 0
            for pattern in target_def['patterns']:
                try:
                    matches = sum(1 for val in sample_data if re.match(pattern, str(val)))
                    pattern_matches = max(pattern_matches, matches)
                except:
                    continue
            
            if pattern_matches > 0:
                validation_score += (pattern_matches / len(sample_data)) * 0.3
                total_checks += 1
        
        return validation_score / max(1, total_checks)
    
    def _looks_like_date(self, value: str) -> bool:
        """Check if a string value looks like a date"""
        if not value or len(value.strip()) < 6:
            return False
        
        # Common date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',      # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',      # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',      # MM-DD-YYYY
            r'\d{8}',                  # YYYYMMDD
            r'\d{2}/\d{2}/\d{2}',      # MM/DD/YY
        ]
        
        return any(re.match(pattern, value.strip()) for pattern in date_patterns)
    
    def _calculate_semantic_similarity(self, source_field: str, target_field: str) -> float:
        """Calculate semantic similarity using keyword matching"""
        # Define semantic keyword groups
        semantic_groups = {
            'identifiers': ['id', 'number', 'no', 'key', 'ref', 'code'],
            'financial': ['amount', 'cost', 'price', 'pay', 'total', 'sum', 'amt'],
            'temporal': ['date', 'time', 'when', 'dt', 'timestamp'],
            'medical': ['diagnosis', 'procedure', 'drug', 'medication', 'treatment'],
            'status': ['status', 'state', 'condition', 'result', 'outcome'],
            'provider': ['provider', 'doctor', 'physician', 'facility', 'hospital'],
            'member': ['member', 'patient', 'person', 'individual', 'client']
        }
        
        # Find which groups each field belongs to
        source_groups = set()
        target_groups = set()
        
        for group_name, keywords in semantic_groups.items():
            if any(keyword in source_field for keyword in keywords):
                source_groups.add(group_name)
            if any(keyword in target_field for keyword in keywords):
                target_groups.add(group_name)
        
        # Calculate similarity based on common groups
        if not source_groups and not target_groups:
            return 0.0
        
        common_groups = source_groups.intersection(target_groups)
        total_groups = source_groups.union(target_groups)
        
        return len(common_groups) / len(total_groups) if total_groups else 0.0
    
    def _generate_transformation_rules(self, 
                                       source_def: Dict[str, Any],
                                       target_def: Dict[str, Any],
                                       parsed_data: pd.DataFrame,
                                       source_field: str) -> List[Dict[str, Any]]:
        """Generate transformation rules needed for mapping"""
        transformation_rules = []
        
        source_type = source_def.get('data_type', 'unknown')
        target_type = target_def.get('data_type', 'unknown')
        
        # Data type conversion rules
        if source_type != target_type:
            if source_type == 'string' and target_type == 'decimal':
                transformation_rules.append({
                    'type': 'convert_to_decimal',
                    'description': 'Convert string to decimal, removing currency symbols',
                    'parameters': {'remove_symbols': ['$', ','], 'decimal_places': 2}
                })
            
            elif source_type == 'string' and target_type == 'date':
                transformation_rules.append({
                    'type': 'parse_date',
                    'description': 'Parse string to date format',
                    'parameters': {'input_formats': ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']}
                })
            
            elif source_type == 'integer' and target_type == 'decimal':
                transformation_rules.append({
                    'type': 'convert_to_decimal',
                    'description': 'Convert integer to decimal',
                    'parameters': {'decimal_places': 2}
                })
        
        # Value standardization rules
        if 'allowed_values' in target_def and parsed_data is not None and source_field in parsed_data.columns:
            sample_values = parsed_data[source_field].dropna().unique()[:10]
            value_mapping = self._create_value_mapping(sample_values, target_def['allowed_values'])
            
            if value_mapping:
                transformation_rules.append({
                    'type': 'map_values',
                    'description': 'Map source values to target allowed values',
                    'parameters': {'value_mapping': value_mapping}
                })
        
        # Length truncation rules
        if 'max_length' in target_def:
            transformation_rules.append({
                'type': 'truncate_length',
                'description': f'Truncate to maximum {target_def["max_length"]} characters',
                'parameters': {'max_length': target_def['max_length']}
            })
        
        # Pattern validation rules
        if 'patterns' in target_def:
            transformation_rules.append({
                'type': 'validate_pattern',
                'description': 'Validate against target field patterns',
                'parameters': {'patterns': target_def['patterns']}
            })
        
        return transformation_rules
    
    def _create_value_mapping(self, source_values: List[str], target_allowed: List[str]) -> Dict[str, str]:
        """Create a mapping between source values and target allowed values"""
        value_mapping = {}
        target_upper = [v.upper() for v in target_allowed]
        
        for source_val in source_values:
            source_str = str(source_val).upper().strip()
            
            # Direct match
            if source_str in target_upper:
                value_mapping[source_val] = target_allowed[target_upper.index(source_str)]
                continue
            
            # Fuzzy matching
            best_match = None
            best_score = 0.0
            
            for target_val in target_allowed:
                score = SequenceMatcher(None, source_str, target_val.upper()).ratio()
                if score > best_score and score > 0.7:
                    best_score = score
                    best_match = target_val
            
            if best_match:
                value_mapping[source_val] = best_match
        
        return value_mapping
    
    def _apply_custom_rules(self, 
                            candidates: List[MappingCandidate],
                            custom_rules: Dict[str, Any]) -> List[MappingCandidate]:
        """Apply custom mapping rules to override or enhance candidates"""
        enhanced_candidates = []
        
        for candidate in candidates:
            # Check if there's a custom rule for this target field
            if candidate.target_field in custom_rules:
                rule = custom_rules[candidate.target_field]
                
                # Boost confidence if source field matches hint
                if 'source_hint' in rule and rule['source_hint'].lower() == candidate.source_field.lower():
                    candidate.confidence_score = min(1.0, candidate.confidence_score + 0.2)
                    candidate.match_reasons.append("Custom rule match")
                
                # Add custom transformation rules
                if 'transformation' in rule:
                    candidate.transformation_rules.append(rule['transformation'])
                
                # Override data type if specified
                if 'data_type' in rule:
                    candidate.data_type = rule['data_type']
            
            enhanced_candidates.append(candidate)
        
        return enhanced_candidates
    
    def _validate_mappings_with_data(self, 
                                     candidates: List[MappingCandidate],
                                     parsed_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Validate mappings against actual data and return validation errors"""
        validation_errors = []
        
        for candidate in candidates:
            if candidate.source_field not in parsed_data.columns:
                continue
            
            data_series = parsed_data[candidate.source_field].dropna()
            if data_series.empty:
                continue
            
            # Sample validation (first 100 records)
            sample_data = data_series.head(100)
            
            target_def = self.schema_fields.get(candidate.target_field, {})
            
            # Validate data type conversion
            if target_def.get('data_type') == 'decimal':
                try:
                    converted = pd.to_numeric(sample_data.astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce')
                    invalid_count = converted.isna().sum()
                    
                    if invalid_count > len(sample_data) * 0.1:  # More than 10% invalid
                        validation_errors.append({
                            'field_name': candidate.source_field,
                            'error_type': 'conversion_error',
                            'error_message': f'{invalid_count}/{len(sample_data)} values cannot be converted to decimal',
                            'sample_value': str(sample_data.iloc[converted.isna().idxmax()]) if invalid_count > 0 else None
                        })
                        
                except Exception as e:
                    validation_errors.append({
                        'field_name': candidate.source_field,
                        'error_type': 'conversion_error',
                        'error_message': f'Failed to convert to decimal: {str(e)}'
                    })
            
            # Validate required field completeness
            if target_def.get('required', False):
                null_percentage = (len(parsed_data) - len(data_series)) / len(parsed_data) * 100
                if null_percentage > 5:  # More than 5% null for required field
                    validation_errors.append({
                        'field_name': candidate.source_field,
                        'error_type': 'completeness_error',
                        'error_message': f'Required field has {null_percentage:.1f}% null values'
                    })
        
        return validation_errors
    
    def _calculate_overall_confidence(self, candidates: List[MappingCandidate]) -> float:
        """Calculate overall confidence score for the mapping set"""
        if not candidates:
            return 0.0
        
        # Weight by target field importance
        important_fields = {'claim_number', 'member_id', 'claim_amount', 'service_date', 'claim_status'}
        
        total_weighted_confidence = 0.0
        total_weight = 0.0
        
        for candidate in candidates:
            weight = 2.0 if candidate.target_field in important_fields else 1.0
            total_weighted_confidence += candidate.confidence_score * weight
            total_weight += weight
        
        return total_weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    def _calculate_data_quality_score(self, validation_errors: List[Dict[str, Any]], total_mappings: int) -> float:
        """Calculate data quality score based on validation results"""
        if total_mappings == 0:
            return 0.0
        
        error_penalty = len(validation_errors) * 0.1
        base_score = 1.0 - (error_penalty / total_mappings)
        
        return max(0.0, min(1.0, base_score))
    
    def _candidate_to_dict(self, candidate: MappingCandidate) -> Dict[str, Any]:
        """Convert MappingCandidate to dictionary format"""
        return {
            'source_field': candidate.source_field,
            'target_field': candidate.target_field,
            'confidence_score': round(candidate.confidence_score, 3),
            'data_type': candidate.data_type,
            'is_required': self.schema_fields.get(candidate.target_field, {}).get('required', False),
            'sample_values': candidate.sample_values,
            'transformation_rules': candidate.transformation_rules,
            'validation_status': 'pending',
            'notes': ' | '.join(candidate.match_reasons),
            'created_by': 'mapping_engine',
            'last_modified': datetime.now().isoformat()
        }


def generate_field_mappings(source_fields: Dict[str, Dict[str, Any]],
                            parsed_data: pd.DataFrame,
                            target_schema: str = "vba_standard",
                            confidence_threshold: float = 0.7,
                            **kwargs) -> Dict[str, Any]:
    """
    Convenience function to generate field mappings
    
    Args:
        source_fields: Source field definitions
        parsed_data: Parsed data for analysis
        target_schema: Target schema ('vba_standard' or 'custom')
        confidence_threshold: Minimum confidence for auto-mapping
        **kwargs: Additional parameters
    
    Returns:
        Mapping generation results
    """
    engine = MappingEngine(target_schema=target_schema)
    return engine.generate_mappings(
        source_fields=source_fields,
        parsed_data=parsed_data,
        confidence_threshold=confidence_threshold,
        **kwargs
    )


def validate_mapping_quality(mappings: List[Dict[str, Any]], 
                             parsed_data: pd.DataFrame,
                             target_schema: str = "vba_standard") -> Dict[str, Any]:
    """
    Validate the quality of existing mappings
    
    Args:
        mappings: List of field mappings to validate
        parsed_data: Source data
        target_schema: Target schema name
    
    Returns:
        Validation results with quality score and issues
    """
    engine = MappingEngine(target_schema=target_schema)
    
    validation_results = {
        'overall_quality_score': 0.0,
        'field_validations': [],
        'data_coverage': {},
        'recommendations': []
    }
    
    try:
        total_score = 0.0
        valid_mappings = 0
        
        for mapping in mappings:
            source_field = mapping['source_field']
            target_field = mapping['target_field']
            
            if source_field not in parsed_data.columns:
                continue
            
            # Validate individual field mapping
            field_score = 0.0
            issues = []
            
            data_series = parsed_data[source_field].dropna()
            
            # Check completeness
            completeness = len(data_series) / len(parsed_data)
            field_score += completeness * 0.4
            
            if completeness < 0.9:
                issues.append(f"Low completeness: {completeness:.1%}")
            
            # Check data type compatibility
            target_def = engine.schema_fields.get(target_field, {})
            if target_def:
                validation_score = engine._validate_sample_data(data_series, target_def)
                field_score += validation_score * 0.6
                
                if validation_score < 0.7:
                    issues.append("Data validation concerns")
            
            validation_results['field_validations'].append({
                'source_field': source_field,
                'target_field': target_field,
                'quality_score': field_score,
                'issues': issues
            })
            
            total_score += field_score
            valid_mappings += 1
        
        # Calculate overall score
        if valid_mappings > 0:
            validation_results['overall_quality_score'] = total_score / valid_mappings
        
        # Generate recommendations
        low_quality_mappings = [fv for fv in validation_results['field_validations'] if fv['quality_score'] < 0.7]
        
        if low_quality_mappings:
            validation_results['recommendations'].append(
                f"Review {len(low_quality_mappings)} mappings with quality scores below 70%"
            )
        
        if validation_results['overall_quality_score'] < 0.8:
            validation_results['recommendations'].append(
                "Consider manual review and adjustment of field mappings"
            )
        
    except Exception as e:
        logger.error(f"Mapping validation failed: {str(e)}")
        validation_results['error'] = str(e)
    
    return validation_results