import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from db import get_db
from models.workspace import Brand, Workspace
from models.social import SocialConnection
from plugins.meta.capabilities.marketing.channel.meta.pages.read.module import MetaPagesReadModule
from routers.runs import _resolve_brief
from config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MetaPageControlValidator:
    """Validator for Meta page control functionality"""
    
    def __init__(self, brand_id: Optional[str] = None):
        self.brand_id = brand_id
        self.settings = get_settings()
        self.db = None
        self._db_gen = None
        
    async def __aenter__(self):
        self._db_gen = get_db()
        async for db in self._db_gen:
            self.db = db
            break
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._db_gen:
            await self._db_gen.aclose()
        if self.db:
            await self.db.close()
            
    async def get_brand_pages(self) -> List[Dict]:
        """Get connected Facebook pages for a brand"""
        if not self.brand_id:
            raise ValueError("Brand ID required for page validation")
            
        # Get brand
        from sqlalchemy import select
        res = await self.db.execute(select(Brand).where(Brand.id == self.brand_id))
        brand = res.scalar_one_or_none()
        if not brand:
            raise ValueError(f"Brand not found: {self.brand_id}")
            
        # Get social connections
        connections = await self.db.execute(
            SocialConnection.__table__.select()
            .where(SocialConnection.brand_id == self.brand_id)
            .where(SocialConnection.platform == 'facebook')
        )
        
        pages = []
        for conn in connections:
            page_info = {
                'connection_id': str(conn.id),
                'page_id': conn.page_id,
                'page_name': conn.page_name,
                'connected_at': conn.connected_at.isoformat(),
                'token_expiry': conn.token_expiry.isoformat() if conn.token_expiry else None,
                'is_active': conn.is_active
            }
            pages.append(page_info)
            
        return pages
    
    async def validate_page_connection(self) -> Dict:
        """Validate Meta OAuth connection and page access"""
        try:
            pages = await self.get_brand_pages()
            
            validation_result = {
                'status': 'success',
                'total_pages': len(pages),
                'pages': pages,
                'connection_status': 'connected' if pages else 'no_connections',
                'errors': []
            }
            
            # Check for expired tokens
            for page in pages:
                if page['token_expiry']:
                    expiry = datetime.fromisoformat(page['token_expiry'])
                    if expiry < datetime.now():
                        validation_result['errors'].append(f"Token expired for page {page['page_name']}")
                    
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating page connection: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'total_pages': 0,
                'pages': [],
                'connection_status': 'error'
            }
    
    async def validate_page_reading(self) -> Dict:
        """Validate page reading capability"""
        try:
            pages = await self.get_brand_pages()
            if not pages:
                return {
                    'status': 'error',
                    'error': 'No connected pages found',
                    'read_results': []
                }
            
            read_results = []
            
            # Test reading each connected page
            for page in pages:
                # Create a test brief with page credentials
                test_brief = {
                    '_channel_credentials': {
                        'facebook_page_token': page.get('access_token'),  # This would come from secure storage
                        'facebook_page_id': page['page_id'],
                        'page_id': page['page_id']
                    },
                    'brand_id': self.brand_id,
                    'workspace_id': 'test-workspace'
                }
                
                # Execute the page reading module
                module = MetaPagesReadModule()
                try:
                    result, artifact = await module.execute_tool_result(test_brief)
                    
                    read_result = {
                        'page_id': page['page_id'],
                        'page_name': page['page_name'],
                        'read_status': 'success',
                        'result': result,
                        'artifact': artifact,
                        'content_preview': artifact.get('content', '')[:200] + '...' if artifact.get('content') else None
                    }
                    
                except Exception as e:
                    logger.error(f"Error during module execution for {page['page_name']}: {e}")
                    read_result = {
                        'page_id': page['page_id'],
                        'page_name': page['page_name'],
                        'read_status': 'failed',
                        'error': str(e),
                        'result': None,
                        'artifact': None
                    }
                
                read_results.append(read_result)
            
            return {
                'status': 'success',
                'total_pages_tested': len(pages),
                'read_results': read_results,
                'success_count': sum(1 for r in read_results if r['read_status'] == 'success'),
                'failure_count': sum(1 for r in read_results if r['read_status'] == 'failed')
            }
            
        except Exception as e:
            logger.error(f"Error validating page reading: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'read_results': []
            }
    
    async def validate_stream_integration(self) -> Dict:
        """Validate integration with Stream UI"""
        try:
            pages = await self.get_brand_pages()
            if not pages:
                return {
                    'status': 'error',
                    'error': 'No connected pages found for Stream integration test'
                }
            
            # Test creating a run that would appear in Stream
            ws = Workspace('test-workspace')
            test_brief = {
                'brand_id': self.brand_id,
                'workspace_id': 'test-workspace',
                'task_name': 'show my facebook page',
                '_channel_credentials': {
                    'facebook_page_token': pages[0].get('access_token'),
                    'facebook_page_id': pages[0]['page_id'],
                    'page_id': pages[0]['page_id']
                }
            }
            
            # Build run brief
            run_brief = await _resolve_brief(self.db, ws, test_brief)
            
            # Create test run (this would be done by the CMO chat normally)
            from models.run import Run, RunResult
            from uuid import uuid4
            
            test_run = Run(
                id=uuid4(),
                module_id='marketing.channel.meta.pages.read',
                status='success',
                approval_status='approved',
                campaign_id=None,
                brand_id=self.brand_id,
                workspace_id='test-workspace',
            )
            
            # Create test result
            module = MetaPagesReadModule()
            try:
                result, artifact = await module.execute_tool_result(test_brief)
            except Exception as e:
                logger.error(f"Module execution failed during stream integration test: {e}")
                return {'status': 'error', 'error': str(e)}
            
            test_result = RunResult(
                run_id=test_run.id,
                content=artifact.get('content', ''),
                self_check_verdict='pass',
                platform='facebook',
                block=artifact.get('block', {}),
            )
            
            # Validate artifact structure for Stream
            stream_validation = {
                'has_block': bool(artifact.get('block')),
                'block_type': artifact.get('block', {}).get('type'),
                'has_content': bool(artifact.get('content')),
                'has_platform': 'facebook' in artifact.get('block', {}).get('platform', ''),
                'has_allowed_actions': bool(artifact.get('block', {}).get('allowed_actions')),
                'allowed_actions': artifact.get('block', {}).get('allowed_actions', []),
                'read_only': artifact.get('block', {}).get('read_only', False)
            }
            
            return {
                'status': 'success',
                'stream_validation': stream_validation,
                'artifact_preview': {
                    'type': stream_validation['block_type'],
                    'content_preview': artifact.get('content', '')[:200] + '...',
                    'allowed_actions': stream_validation['allowed_actions']
                }
            }
            
        except Exception as e:
            logger.error(f"Error validating Stream integration: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'stream_validation': {}
            }
    
    async def run_full_validation(self) -> Dict:
        """Run all validation tests"""
        logger.info("Starting comprehensive Meta page control validation")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'brand_id': self.brand_id,
            'tests': {}
        }
        
        # Test 1: Page Connection
        logger.info("Testing page connection...")
        results['tests']['page_connection'] = await self.validate_page_connection()
        
        # Test 2: Page Reading
        logger.info("Testing page reading...")
        results['tests']['page_reading'] = await self.validate_page_reading()
        
        # Test 3: Stream Integration
        logger.info("Testing Stream integration...")
        results['tests']['stream_integration'] = await self.validate_stream_integration()
        
        # Summary
        all_tests = results['tests']
        successful_tests = sum(1 for test in all_tests.values() if test.get('status') == 'success')
        total_tests = len(all_tests)
        
        results['summary'] = {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'failed_tests': total_tests - successful_tests,
            'success_rate': (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        }
        
        logger.info(f"Validation complete: {successful_tests}/{total_tests} tests passed")
        return results

async def main():
    """Main validation function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Meta page control functionality')
    parser.add_argument('--brand-id', help='Brand ID to test')
    parser.add_argument('--test-page-connection', action='store_true', help='Test page connection only')
    parser.add_argument('--test-page-read', action='store_true', help='Test page reading only')
    parser.add_argument('--test-stream-integration', action='store_true', help='Test Stream integration only')
    parser.add_argument('--output', help='Output file for validation results')
    
    args = parser.parse_args()
    
    async with MetaPageControlValidator(brand_id=args.brand_id) as validator:
        if args.test_page_connection:
            results = await validator.validate_page_connection()
        elif args.test_page_read:
            results = await validator.validate_page_reading()
        elif args.test_stream_integration:
            results = await validator.validate_stream_integration()
        else:
            results = await validator.run_full_validation()
    
    # Output results
    print("\n" + "="*50)
    print("META PAGE CONTROL VALIDATION RESULTS")
    print("="*50)
    print(json.dumps(results, indent=2))
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    # Return exit code based on success
    exit_code = 0 if results.get('summary', {}).get('success_rate', 0) == 100 else 1
    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(main())
