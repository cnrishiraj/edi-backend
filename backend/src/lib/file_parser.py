"""
SmithRx file parser library with pandas integration
Handles parsing of EDI files and field definition extraction
"""
import pandas as pd
import numpy as np
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
import logging
from io import StringIO, BytesIO
import csv


logger = logging.getLogger(__name__)


class CompanionDocsParser:
    """Parser for companion Excel documentation files containing field definitions"""
    
    def __init__(self, excel_file_path: Union[str, Path, BytesIO]):
        self.excel_file_path = excel_file_path
        self.field_definitions: Dict[str, Dict[str, Any]] = {}
        self.schema_mappings: Dict[str, str] = {}
        self.validation_rules: Dict[str, Dict[str, Any]] = {}
        
    def parse_companion_docs(self) -> Dict[str, Any]:
        """
        Parse companion Excel documentation to extract field definitions
        
        Returns:
            Dictionary containing field definitions, mappings, and validation rules
        """
        try:
            logger.info("Starting to parse companion Excel documentation")
            
            # Load Excel file with all sheets
            if isinstance(self.excel_file_path, BytesIO):
                excel_data = pd.read_excel(self.excel_file_path, sheet_name=None, dtype=str)
            else:
                excel_data = pd.read_excel(self.excel_file_path, sheet_name=None, dtype=str)
            
            # Process different types of sheets
            for sheet_name, df in excel_data.items():
                sheet_name_lower = sheet_name.lower()
                
                if 'field' in sheet_name_lower and ('definition' in sheet_name_lower or 'mapping' in sheet_name_lower):
                    self._parse_field_definitions(df, sheet_name)
                elif 'schema' in sheet_name_lower or 'mapping' in sheet_name_lower:
                    self._parse_schema_mappings(df, sheet_name)
                elif 'validation' in sheet_name_lower or 'rule' in sheet_name_lower:
                    self._parse_validation_rules(df, sheet_name)
                else:
                    # Try to auto-detect content type
                    self._auto_detect_sheet_content(df, sheet_name)
            
            result = {
                'field_definitions': self.field_definitions,
                'schema_mappings': self.schema_mappings,
                'validation_rules': self.validation_rules,
                'parsed_sheets': list(excel_data.keys()),
                'total_fields_defined': len(self.field_definitions)
            }
            
            logger.info(f"Successfully parsed companion docs: {len(self.field_definitions)} field definitions found")
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse companion docs: {str(e)}")
            raise Exception(f"Companion docs parsing failed: {str(e)}")
    
    def _parse_field_definitions(self, df: pd.DataFrame, sheet_name: str) -> None:
        """Parse field definitions from Excel sheet"""
        try:
            # Common column name patterns for field definitions
            field_col_patterns = ['field', 'field_name', 'column', 'column_name', 'name']
            description_col_patterns = ['description', 'desc', 'definition', 'meaning', 'purpose']
            type_col_patterns = ['type', 'data_type', 'datatype', 'format']
            required_col_patterns = ['required', 'mandatory', 'optional', 'nullable']
            
            # Find actual column names that match patterns
            field_col = self._find_column_by_patterns(df, field_col_patterns)
            description_col = self._find_column_by_patterns(df, description_col_patterns)
            type_col = self._find_column_by_patterns(df, type_col_patterns)
            required_col = self._find_column_by_patterns(df, required_col_patterns)
            
            if not field_col:
                logger.warning(f"No field name column found in sheet '{sheet_name}'")
                return
            
            for _, row in df.iterrows():
                field_name = str(row.get(field_col, '')).strip()
                if field_name and field_name.lower() not in ['field', 'field_name', 'nan']:
                    
                    # Clean field name
                    clean_field_name = field_name.lower().replace(' ', '_').replace('-', '_')
                    
                    self.field_definitions[clean_field_name] = {
                        'original_name': field_name,
                        'description': str(row.get(description_col, '')).strip() if description_col else '',
                        'data_type': str(row.get(type_col, 'string')).strip().lower() if type_col else 'string',
                        'required': self._parse_boolean(str(row.get(required_col, 'false'))) if required_col else False,
                        'source_sheet': sheet_name,
                        'examples': [],  # Can be enhanced to parse example values
                        'validation_rules': {}
                    }
            
            logger.info(f"Parsed {len([k for k, v in self.field_definitions.items() if v['source_sheet'] == sheet_name])} field definitions from '{sheet_name}'")
            
        except Exception as e:
            logger.warning(f"Failed to parse field definitions from sheet '{sheet_name}': {str(e)}")
    
    def _parse_schema_mappings(self, df: pd.DataFrame, sheet_name: str) -> None:
        """Parse schema mappings from Excel sheet"""
        try:
            source_col_patterns = ['source', 'source_field', 'smithrx', 'input']
            target_col_patterns = ['target', 'target_field', 'vba', 'output', 'destination']
            
            source_col = self._find_column_by_patterns(df, source_col_patterns)
            target_col = self._find_column_by_patterns(df, target_col_patterns)
            
            if source_col and target_col:
                for _, row in df.iterrows():
                    source_field = str(row.get(source_col, '')).strip()
                    target_field = str(row.get(target_col, '')).strip()
                    
                    if source_field and target_field and source_field.lower() != 'nan':
                        self.schema_mappings[source_field.lower()] = target_field
                
                logger.info(f"Parsed {len(self.schema_mappings)} schema mappings from '{sheet_name}'")
            
        except Exception as e:
            logger.warning(f"Failed to parse schema mappings from sheet '{sheet_name}': {str(e)}")
    
    def _parse_validation_rules(self, df: pd.DataFrame, sheet_name: str) -> None:
        """Parse validation rules from Excel sheet"""
        try:
            field_col = self._find_column_by_patterns(df, ['field', 'field_name'])
            rule_col = self._find_column_by_patterns(df, ['rule', 'validation', 'constraint'])
            
            if field_col and rule_col:
                for _, row in df.iterrows():
                    field_name = str(row.get(field_col, '')).strip()
                    rule = str(row.get(rule_col, '')).strip()
                    
                    if field_name and rule and field_name.lower() != 'nan':
                        if field_name.lower() not in self.validation_rules:
                            self.validation_rules[field_name.lower()] = {}
                        
                        # Parse different types of validation rules
                        if 'length' in rule.lower():
                            self.validation_rules[field_name.lower()]['max_length'] = self._extract_number(rule)
                        elif 'format' in rule.lower() or 'pattern' in rule.lower():
                            self.validation_rules[field_name.lower()]['format'] = rule
                        else:
                            self.validation_rules[field_name.lower()]['custom'] = rule
            
        except Exception as e:
            logger.warning(f"Failed to parse validation rules from sheet '{sheet_name}': {str(e)}")
    
    def _auto_detect_sheet_content(self, df: pd.DataFrame, sheet_name: str) -> None:
        """Auto-detect sheet content type and parse accordingly"""
        try:
            columns = [col.lower() for col in df.columns]
            
            # Check for field definition patterns
            if any(pattern in columns for pattern in ['field', 'field_name', 'column']) and \
               any(pattern in columns for pattern in ['description', 'definition', 'type']):
                self._parse_field_definitions(df, sheet_name)
                
            # Check for mapping patterns
            elif any(pattern in columns for pattern in ['source', 'smithrx']) and \
                 any(pattern in columns for pattern in ['target', 'vba', 'destination']):
                self._parse_schema_mappings(df, sheet_name)
                
        except Exception as e:
            logger.warning(f"Failed to auto-detect content type for sheet '{sheet_name}': {str(e)}")
    
    def _find_column_by_patterns(self, df: pd.DataFrame, patterns: List[str]) -> Optional[str]:
        """Find column name that matches any of the given patterns"""
        columns = df.columns.tolist()
        for col in columns:
            col_lower = col.lower()
            for pattern in patterns:
                if pattern in col_lower:
                    return col
        return None
    
    def _parse_boolean(self, value: str) -> bool:
        """Parse boolean value from string"""
        value_lower = value.lower().strip()
        return value_lower in ['true', 'yes', '1', 'required', 'mandatory', 'y']
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text"""
        import re
        numbers = re.findall(r'\d+', text)
        return int(numbers[0]) if numbers else None


class SmithRxParser:
    """Parser for SmithRx claims files"""
    
    # Common SmithRx field patterns and variations
    FIELD_MAPPINGS = {
        # Claim identifiers
        'claim_id': ['CLAIM_ID', 'CLAIMID', 'CLAIM_NO', 'CLMNO', 'CLAIM_NUMBER'],
        'member_id': ['MEMBER_ID', 'MEMBERID', 'MBR_ID', 'MBRID', 'MEMBER_NUMBER'],
        'provider_id': ['PROVIDER_ID', 'PROVIDERID', 'PRV_ID', 'PRVID', 'PROVIDER_NUMBER'],
        
        # Financial fields
        'claim_amount': ['AMOUNT', 'CLAIM_AMOUNT', 'CLAIMAMOUNT', 'AMT', 'CLAIM_AMT', 'TOTAL_AMOUNT'],
        'copay_amount': ['COPAY', 'COPAY_AMOUNT', 'COPAYAMT', 'COPAY_AMT', 'COINSURANCE'],
        'deductible': ['DEDUCTIBLE', 'DEDUCTIBLE_AMOUNT', 'DEDUCT', 'DEDUCT_AMT'],
        
        # Date fields
        'service_date': ['SERVICE_DATE', 'SERVICEDATE', 'SVC_DATE', 'SVCDT', 'DATE_OF_SERVICE'],
        'process_date': ['PROCESS_DATE', 'PROCESSDATE', 'PROC_DATE', 'PROCESSED_DATE'],
        'paid_date': ['PAID_DATE', 'PAIDDATE', 'PAYMENT_DATE', 'PAY_DATE'],
        
        # Medical codes
        'diagnosis_code': ['DIAGNOSIS_CODE', 'DIAGCODE', 'DIAG_CODE', 'ICD_CODE', 'DX_CODE'],
        'procedure_code': ['PROCEDURE_CODE', 'PROCCODE', 'PROC_CODE', 'CPT_CODE'],
        'drug_code': ['DRUG_CODE', 'DRUGCODE', 'NDC_CODE', 'NDC', 'MEDICATION_CODE'],
        
        # Status and processing
        'claim_status': ['STATUS', 'CLAIM_STATUS', 'STS', 'PROCESSING_STATUS'],
        'rejection_code': ['REJECTION_CODE', 'REJECT_CODE', 'DENY_CODE', 'ERROR_CODE'],
    }
    
    # Date format patterns
    DATE_FORMATS = [
        '%Y-%m-%d',      # 2024-01-15
        '%m/%d/%Y',      # 01/15/2024
        '%m-%d-%Y',      # 01-15-2024
        '%Y%m%d',        # 20240115
        '%m/%d/%y',      # 01/15/24
        '%d/%m/%Y',      # 15/01/2024 (European)
        '%Y/%m/%d',      # 2024/01/15
    ]
    
    def __init__(self, file_path: Union[str, Path, BytesIO], file_type: str = "smithrx_claims", companion_docs: Optional[BytesIO] = None):
        self.file_path = file_path
        self.file_type = file_type
        self.companion_docs = companion_docs
        self.raw_data: Optional[pd.DataFrame] = None
        self.parsed_data: Optional[pd.DataFrame] = None
        self.field_definitions: Dict[str, Dict[str, Any]] = {}
        self.companion_field_definitions: Dict[str, Dict[str, Any]] = {}
        self.schema_mappings: Dict[str, str] = {}
        self.parsing_errors: List[str] = []
        self.parsing_warnings: List[str] = []
        self.file_metadata: Dict[str, Any] = {}
        
    def parse_file(self) -> Dict[str, Any]:
        """
        Main parsing method that coordinates the entire parsing process
        
        Returns:
            Dict containing parsed data, metadata, and statistics
        """
        try:
            logger.info(f"Starting to parse file: {self.file_path}")
            
            # Step 0: Parse companion docs if provided
            if self.companion_docs:
                self._parse_companion_documentation()
            
            # Step 1: Detect file format and load raw data
            self._detect_and_load_file()
            
            # Step 2: Clean and validate data
            self._clean_and_validate_data()
            
            # Step 3: Extract field definitions
            self._extract_field_definitions()
            
            # Step 4: Standardize field names
            self._standardize_field_names()
            
            # Step 5: Parse and convert data types
            self._parse_data_types()
            
            # Step 6: Generate file statistics
            file_stats = self._generate_file_statistics()
            
            logger.info(f"Successfully parsed file with {len(self.parsed_data)} records")
            
            return {
                'success': True,
                'data': self.parsed_data,
                'field_definitions': self.field_definitions,
                'file_metadata': self.file_metadata,
                'statistics': file_stats,
                'errors': self.parsing_errors,
                'warnings': self.parsing_warnings
            }
            
        except Exception as e:
            logger.error(f"Failed to parse file: {str(e)}")
            self.parsing_errors.append(f"Parse failure: {str(e)}")
            return {
                'success': False,
                'data': None,
                'field_definitions': {},
                'file_metadata': self.file_metadata,
                'statistics': {},
                'errors': self.parsing_errors,
                'warnings': self.parsing_warnings
            }
    
    def _detect_and_load_file(self) -> None:
        """Detect file format and load raw data"""
        try:
            if isinstance(self.file_path, BytesIO):
                # Handle BytesIO object
                content = self.file_path.getvalue()
                self.file_metadata['file_size'] = len(content)
                
                # Detect file type by content
                file_type = self._detect_file_type_from_content(content)
                self.file_metadata['detected_format'] = file_type
                
                if file_type == 'excel':
                    # Load Excel file
                    self.file_path.seek(0)  # Reset position
                    self.raw_data = pd.read_excel(self.file_path, dtype=str)
                    self.file_metadata['encoding'] = 'excel'
                    
                else:
                    # Handle as CSV/text
                    if isinstance(content, bytes):
                        content = content.decode('utf-8', errors='ignore')
                    self.file_metadata['encoding'] = 'utf-8'
                    
                    # Try to detect delimiter
                    delimiter = self._detect_delimiter(content[:1000])
                    self.file_metadata['delimiter'] = delimiter
                    
                    # Load data
                    self.raw_data = pd.read_csv(StringIO(content), delimiter=delimiter, dtype=str)
                
            else:
                # Handle file path
                file_path = Path(self.file_path)
                self.file_metadata['file_size'] = file_path.stat().st_size
                self.file_metadata['original_filename'] = file_path.name
                
                # Detect file type by extension and content
                file_extension = file_path.suffix.lower()
                if file_extension in ['.xlsx', '.xls']:
                    # Load Excel file
                    self.raw_data = pd.read_excel(file_path, dtype=str)
                    self.file_metadata['detected_format'] = 'excel'
                    self.file_metadata['encoding'] = 'excel'
                else:
                    # Handle as CSV/text
                    encoding = self._detect_encoding(file_path)
                    self.file_metadata['encoding'] = encoding
                    
                    # Read first few lines to detect format
                    with open(file_path, 'r', encoding=encoding) as f:
                        sample_content = f.read(2000)
                    
                    # Detect delimiter
                    delimiter = self._detect_delimiter(sample_content)
                    self.file_metadata['delimiter'] = delimiter
                    self.file_metadata['detected_format'] = 'csv'
                    
                    # Load full data
                    self.raw_data = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, dtype=str)
            
            self.file_metadata['record_count'] = len(self.raw_data)
            self.file_metadata['field_count'] = len(self.raw_data.columns)
            self.file_metadata['has_header'] = self._has_header_row()
            
            logger.info(f"Loaded {len(self.raw_data)} records with {len(self.raw_data.columns)} fields")
            
        except Exception as e:
            raise Exception(f"Failed to load file: {str(e)}")
    
    def _parse_companion_documentation(self) -> None:
        """Parse companion Excel documentation for field definitions"""
        try:
            logger.info("Processing companion documentation")
            
            companion_parser = CompanionDocsParser(self.companion_docs)
            companion_result = companion_parser.parse_companion_docs()
            
            # Store companion docs results
            self.companion_field_definitions = companion_result['field_definitions']
            self.schema_mappings = companion_result['schema_mappings']
            
            # Update file metadata with companion docs info
            self.file_metadata['companion_docs'] = {
                'parsed_sheets': companion_result['parsed_sheets'],
                'field_definitions_count': companion_result['total_fields_defined'],
                'schema_mappings_count': len(companion_result['schema_mappings']),
                'has_validation_rules': len(companion_result['validation_rules']) > 0
            }
            
            logger.info(f"Parsed companion docs: {len(self.companion_field_definitions)} field definitions, {len(self.schema_mappings)} mappings")
            
        except Exception as e:
            logger.warning(f"Failed to parse companion documentation: {str(e)}")
            self.parsing_warnings.append(f"Companion docs parsing failed: {str(e)}")
    
    def _detect_delimiter(self, sample_content: str) -> str:
        """Detect the delimiter used in the file"""
        common_delimiters = [',', '|', '\t', ';', ':']
        delimiter_counts = {}
        
        for delimiter in common_delimiters:
            count = sample_content.count(delimiter)
            if count > 0:
                delimiter_counts[delimiter] = count
        
        if delimiter_counts:
            # Return the most common delimiter
            return max(delimiter_counts.keys(), key=delimiter_counts.get)
        else:
            return ','  # Default to comma
    
    def _detect_file_type_from_content(self, content: bytes) -> str:
        """Detect file type based on content magic bytes"""
        # Excel file signatures
        excel_signatures = [
            b'PK\x03\x04',  # Modern Excel (.xlsx)
            b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',  # Legacy Excel (.xls)
            b'PK',  # General ZIP-based (includes .xlsx)
        ]
        
        # Check first few bytes for Excel signatures
        for signature in excel_signatures:
            if content.startswith(signature):
                return 'excel'
        
        # Check if it looks like CSV/text content
        try:
            text_content = content.decode('utf-8', errors='ignore')[:1000]
            # Look for common CSV patterns
            if (',' in text_content or '|' in text_content or '\t' in text_content):
                return 'csv'
        except:
            pass
        
        return 'csv'  # Default fallback
    
    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding"""
        try:
            import chardet
            with open(file_path, 'rb') as f:
                result = chardet.detect(f.read(10000))
                return result['encoding'] or 'utf-8'
        except ImportError:
            # Fallback if chardet not available
            encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        f.read(1000)
                    return encoding
                except UnicodeDecodeError:
                    continue
            return 'utf-8'
    
    def _has_header_row(self) -> bool:
        """Determine if the first row contains headers"""
        if self.raw_data is None or len(self.raw_data) == 0:
            return False
        
        first_row = self.raw_data.iloc[0]
        
        # Check if first row contains common header patterns
        header_indicators = ['ID', 'NUMBER', 'DATE', 'AMOUNT', 'CODE', 'NAME', 'STATUS']
        header_score = sum(1 for val in first_row if any(indicator in str(val).upper() for indicator in header_indicators))
        
        # If more than 50% of first row values look like headers, assume it's a header row
        return header_score > len(first_row) * 0.5
    
    def _clean_and_validate_data(self) -> None:
        """Clean and validate the raw data"""
        if self.raw_data is None:
            raise Exception("No raw data to clean")
        
        original_count = len(self.raw_data)
        
        # Remove completely empty rows
        self.raw_data = self.raw_data.dropna(how='all')
        
        # Remove duplicate rows
        duplicate_count = self.raw_data.duplicated().sum()
        if duplicate_count > 0:
            self.raw_data = self.raw_data.drop_duplicates()
            self.parsing_warnings.append(f"Removed {duplicate_count} duplicate rows")
        
        # Clean column names
        self.raw_data.columns = [str(col).strip().upper().replace(' ', '_') for col in self.raw_data.columns]
        
        cleaned_count = len(self.raw_data)
        if cleaned_count != original_count:
            self.parsing_warnings.append(f"Data cleaning reduced records from {original_count} to {cleaned_count}")
        
        # Make a copy for parsing
        self.parsed_data = self.raw_data.copy()
    
    def _extract_field_definitions(self) -> None:
        """Extract field definitions from the data, enhanced with companion docs"""
        if self.parsed_data is None:
            return
        
        # First, incorporate companion docs field definitions
        if self.companion_field_definitions:
            logger.info("Enriching field definitions with companion documentation")
        
        for column in self.parsed_data.columns:
            # Get sample values (non-null, unique)
            sample_values = self.parsed_data[column].dropna().unique()[:10]
            sample_values = [str(val) for val in sample_values if str(val).strip()]
            
            # Analyze data type patterns
            data_type = self._analyze_data_type(self.parsed_data[column])
            
            # Calculate statistics
            null_count = self.parsed_data[column].isnull().sum()
            unique_count = self.parsed_data[column].nunique()
            
            # Detect if it's a standardized field
            standardized_name = self._map_to_standard_field(column)
            
            # Check if we have companion docs definition for this field
            companion_def = None
            column_lower = column.lower().replace(' ', '_').replace('-', '_')
            if self.companion_field_definitions:
                companion_def = self.companion_field_definitions.get(column_lower)
                if not companion_def:
                    # Try fuzzy matching for field names
                    for comp_field, comp_def in self.companion_field_definitions.items():
                        if comp_field in column_lower or column_lower in comp_field:
                            companion_def = comp_def
                            break
            
            # Build field definition with companion docs enhancement
            field_def = {
                'original_name': column,
                'standardized_name': standardized_name,
                'data_type': data_type,
                'sample_values': sample_values[:5],  # First 5 samples
                'null_count': null_count,
                'unique_count': unique_count,
                'total_count': len(self.parsed_data),
                'null_percentage': round(null_count / len(self.parsed_data) * 100, 2),
                'is_key_field': self._is_key_field(column, unique_count, len(self.parsed_data))
            }
            
            # Enhance with companion docs if available
            if companion_def:
                field_def.update({
                    'description': companion_def.get('description', ''),
                    'expected_data_type': companion_def.get('data_type', data_type),
                    'is_required': companion_def.get('required', False),
                    'companion_source': companion_def.get('source_sheet', ''),
                    'has_companion_definition': True,
                    'data_type_matches': companion_def.get('data_type', data_type).lower() == data_type.lower()
                })
            else:
                field_def['has_companion_definition'] = False
            
            # Add schema mapping if available
            if self.schema_mappings:
                mapped_field = self.schema_mappings.get(column_lower)
                if mapped_field:
                    field_def['vba_mapping'] = mapped_field
                    field_def['has_vba_mapping'] = True
                else:
                    field_def['has_vba_mapping'] = False
            
            self.field_definitions[column] = field_def
    
    def _analyze_data_type(self, series: pd.Series) -> str:
        """Analyze the data type of a series"""
        non_null_series = series.dropna()
        if len(non_null_series) == 0:
            return 'unknown'
        
        sample_values = non_null_series.iloc[:100].astype(str)
        
        # Check for dates
        date_count = sum(1 for val in sample_values if self._is_date_like(val))
        if date_count > len(sample_values) * 0.8:
            return 'date'
        
        # Check for numbers
        numeric_count = sum(1 for val in sample_values if self._is_numeric(val))
        if numeric_count > len(sample_values) * 0.8:
            # Check if it's integer or decimal
            decimal_count = sum(1 for val in sample_values if '.' in str(val) and self._is_numeric(val))
            return 'decimal' if decimal_count > 0 else 'integer'
        
        # Check for boolean-like values
        bool_values = set(str(val).upper() for val in sample_values)
        if bool_values.issubset({'TRUE', 'FALSE', 'T', 'F', 'Y', 'N', 'YES', 'NO', '1', '0'}):
            return 'boolean'
        
        return 'string'
    
    def _is_date_like(self, value: str) -> bool:
        """Check if a value looks like a date"""
        if not value or len(str(value).strip()) < 6:
            return False
        
        for date_format in self.DATE_FORMATS:
            try:
                datetime.strptime(str(value).strip(), date_format)
                return True
            except ValueError:
                continue
        
        # Check for common date patterns with regex
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{8}',              # YYYYMMDD
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, str(value).strip()):
                return True
        
        return False
    
    def _is_numeric(self, value: str) -> bool:
        """Check if a value is numeric"""
        try:
            float(str(value).replace(',', '').replace('$', '').strip())
            return True
        except (ValueError, TypeError):
            return False
    
    def _map_to_standard_field(self, field_name: str) -> Optional[str]:
        """Map field name to standardized name"""
        field_name_upper = field_name.upper()
        
        for standard_name, variations in self.FIELD_MAPPINGS.items():
            if field_name_upper in variations:
                return standard_name
        
        return None
    
    def _is_key_field(self, field_name: str, unique_count: int, total_count: int) -> bool:
        """Determine if a field is likely a key field"""
        uniqueness_ratio = unique_count / total_count if total_count > 0 else 0
        
        # Fields with high uniqueness are likely keys
        if uniqueness_ratio > 0.95:
            return True
        
        # Fields with ID-like names are likely keys
        key_indicators = ['ID', 'NUMBER', 'KEY', 'CODE']
        if any(indicator in field_name.upper() for indicator in key_indicators):
            return uniqueness_ratio > 0.8
        
        return False
    
    def _standardize_field_names(self) -> None:
        """Standardize field names based on mappings"""
        if self.parsed_data is None:
            return
        
        rename_mapping = {}
        for column in self.parsed_data.columns:
            standard_name = self._map_to_standard_field(column)
            if standard_name and standard_name != column.lower():
                # Create a unique standardized name if there are conflicts
                if standard_name in rename_mapping.values():
                    standard_name = f"{standard_name}_alt"
                rename_mapping[column] = standard_name
        
        if rename_mapping:
            self.parsed_data = self.parsed_data.rename(columns=rename_mapping)
            self.parsing_warnings.append(f"Renamed {len(rename_mapping)} fields to standard names")
    
    def _parse_data_types(self) -> None:
        """Parse and convert data types"""
        if self.parsed_data is None:
            return
        
        for column in self.parsed_data.columns:
            field_def = self.field_definitions.get(column, {})
            data_type = field_def.get('data_type', 'string')
            
            try:
                if data_type == 'date':
                    self.parsed_data[column] = self._parse_date_column(self.parsed_data[column])
                elif data_type == 'integer':
                    self.parsed_data[column] = pd.to_numeric(self.parsed_data[column], errors='coerce').astype('Int64')
                elif data_type == 'decimal':
                    # Clean currency symbols and convert to float
                    cleaned_values = self.parsed_data[column].astype(str).str.replace(r'[$,]', '', regex=True)
                    self.parsed_data[column] = pd.to_numeric(cleaned_values, errors='coerce')
                elif data_type == 'boolean':
                    self.parsed_data[column] = self._parse_boolean_column(self.parsed_data[column])
                
            except Exception as e:
                self.parsing_warnings.append(f"Failed to convert {column} to {data_type}: {str(e)}")
    
    def _parse_date_column(self, series: pd.Series) -> pd.Series:
        """Parse a date column trying multiple formats"""
        parsed_series = pd.Series(index=series.index, dtype='datetime64[ns]')
        
        for date_format in self.DATE_FORMATS:
            mask = parsed_series.isnull()
            if not mask.any():
                break
            
            try:
                parsed_values = pd.to_datetime(series[mask], format=date_format, errors='coerce')
                parsed_series[mask] = parsed_values
            except:
                continue
        
        return parsed_series
    
    def _parse_boolean_column(self, series: pd.Series) -> pd.Series:
        """Parse a boolean column"""
        boolean_mapping = {
            'TRUE': True, 'FALSE': False,
            'T': True, 'F': False,
            'Y': True, 'N': False,
            'YES': True, 'NO': False,
            '1': True, '0': False
        }
        
        return series.astype(str).str.upper().map(boolean_mapping)
    
    def _generate_file_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive file statistics"""
        if self.parsed_data is None:
            return {}
        
        stats = {
            'record_count': len(self.parsed_data),
            'field_count': len(self.parsed_data.columns),
            'file_size_bytes': self.file_metadata.get('file_size', 0),
            'data_quality_score': self._calculate_data_quality_score(),
            'field_types': {},
            'key_fields': [],
            'date_range': {},
            'numeric_ranges': {},
            'completeness_scores': {}
        }
        
        # Field type distribution
        for field_name, field_def in self.field_definitions.items():
            data_type = field_def['data_type']
            if data_type not in stats['field_types']:
                stats['field_types'][data_type] = 0
            stats['field_types'][data_type] += 1
            
            # Track key fields
            if field_def['is_key_field']:
                stats['key_fields'].append(field_name)
            
            # Completeness score
            null_percentage = field_def['null_percentage']
            stats['completeness_scores'][field_name] = round(100 - null_percentage, 2)
        
        # Date ranges for date fields
        date_fields = [name for name, def_ in self.field_definitions.items() if def_['data_type'] == 'date']
        for field in date_fields:
            if field in self.parsed_data.columns:
                date_series = self.parsed_data[field].dropna()
                if len(date_series) > 0:
                    stats['date_range'][field] = {
                        'min_date': str(date_series.min()),
                        'max_date': str(date_series.max()),
                        'span_days': (date_series.max() - date_series.min()).days
                    }
        
        # Numeric ranges for numeric fields
        numeric_fields = [name for name, def_ in self.field_definitions.items() 
                         if def_['data_type'] in ['integer', 'decimal']]
        for field in numeric_fields:
            if field in self.parsed_data.columns:
                numeric_series = self.parsed_data[field].dropna()
                if len(numeric_series) > 0:
                    stats['numeric_ranges'][field] = {
                        'min_value': float(numeric_series.min()),
                        'max_value': float(numeric_series.max()),
                        'mean_value': float(numeric_series.mean()),
                        'median_value': float(numeric_series.median())
                    }
        
        return stats
    
    def _calculate_data_quality_score(self) -> float:
        """Calculate overall data quality score (0-100)"""
        if not self.field_definitions:
            return 0.0
        
        total_score = 0
        field_count = len(self.field_definitions)
        
        for field_def in self.field_definitions.values():
            field_score = 100 - field_def['null_percentage']  # Completeness
            
            # Bonus for standardized fields
            if field_def['standardized_name']:
                field_score = min(100, field_score * 1.1)
            
            # Penalty for too many nulls
            if field_def['null_percentage'] > 50:
                field_score *= 0.7
            
            total_score += field_score
        
        return round(total_score / field_count, 2) if field_count > 0 else 0.0
    
    def get_content_hash(self) -> str:
        """Generate content hash for duplicate detection"""
        if self.raw_data is None:
            return ""
        
        # Create a hash based on the data content
        content_str = str(self.raw_data.values.tobytes())
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def export_parsed_data(self, format: str = 'csv') -> bytes:
        """Export parsed data in specified format"""
        if self.parsed_data is None:
            raise Exception("No parsed data available for export")
        
        if format.lower() == 'csv':
            return self.parsed_data.to_csv(index=False).encode('utf-8')
        elif format.lower() == 'json':
            return self.parsed_data.to_json(orient='records').encode('utf-8')
        elif format.lower() == 'xlsx':
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                self.parsed_data.to_excel(writer, index=False)
            return buffer.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")


def parse_smithrx_file(file_path: Union[str, Path, BytesIO], 
                       file_type: str = "smithrx_claims") -> Dict[str, Any]:
    """
    Convenience function to parse SmithRx files
    
    Args:
        file_path: Path to file or BytesIO object
        file_type: Type of file (default: smithrx_claims)
    
    Returns:
        Dictionary with parsing results
    """
    parser = SmithRxParser(file_path, file_type)
    return parser.parse_file()


def validate_smithrx_format(file_path: Union[str, Path, BytesIO]) -> Dict[str, Any]:
    """
    Validate if a file appears to be in SmithRx format
    
    Returns:
        Validation result with boolean and details
    """
    try:
        parser = SmithRxParser(file_path)
        parser._detect_and_load_file()
        
        if parser.raw_data is None or len(parser.raw_data) == 0:
            return {
                'is_valid': False,
                'errors': ['File is empty or could not be read'],
                'warnings': []
            }
        
        # Check for common SmithRx patterns
        columns = [col.upper() for col in parser.raw_data.columns]
        
        # Must have at least some key fields
        required_patterns = ['CLAIM', 'MEMBER', 'AMOUNT']
        found_patterns = sum(1 for pattern in required_patterns 
                           if any(pattern in col for col in columns))
        
        if found_patterns < 2:
            return {
                'is_valid': False,
                'errors': ['File does not appear to contain SmithRx claims data'],
                'warnings': []
            }
        
        return {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'detected_fields': len(columns),
            'record_count': len(parser.raw_data)
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'errors': [f'Validation failed: {str(e)}'],
            'warnings': []
        }