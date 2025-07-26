#!/usr/bin/env python3
"""
Script to clean GitHub API branch protection backup for restoration.
The GET response includes metadata that the PUT endpoint doesn't accept.
"""
import json
import sys

def clean_protection_backup(input_file, output_file):
    """Clean the protection backup for restoration."""
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Extract only the fields needed for PUT request
    cleaned = {}
    
    # Handle required_status_checks
    if 'required_status_checks' in data and data['required_status_checks']:
        rsc = data['required_status_checks']
        cleaned['required_status_checks'] = {
            'strict': rsc.get('strict', False),
            'contexts': rsc.get('contexts', []),
            'checks': rsc.get('checks', [])
        }
    else:
        cleaned['required_status_checks'] = None
    
    # Handle required_pull_request_reviews
    if 'required_pull_request_reviews' in data and data['required_pull_request_reviews']:
        rpr = data['required_pull_request_reviews']
        cleaned['required_pull_request_reviews'] = {}
        
        # Only include fields that are settable
        settable_fields = [
            'dismiss_stale_reviews', 'require_code_owner_reviews', 
            'required_approving_review_count', 'require_last_push_approval'
        ]
        
        for field in settable_fields:
            if field in rpr:
                cleaned['required_pull_request_reviews'][field] = rpr[field]
        
        # Handle dismissal_restrictions if present
        if 'dismissal_restrictions' in rpr:
            cleaned['required_pull_request_reviews']['dismissal_restrictions'] = rpr['dismissal_restrictions']
    
    # Handle other boolean/simple fields
    boolean_fields = [
        'enforce_admins', 'required_linear_history', 'allow_force_pushes',
        'allow_deletions', 'required_conversation_resolution', 'lock_branch',
        'allow_fork_syncing'
    ]
    
    for field in boolean_fields:
        if field in data:
            if isinstance(data[field], dict) and 'enabled' in data[field]:
                cleaned[field] = data[field]['enabled']
            else:
                cleaned[field] = data[field]
    
    # Handle restrictions
    cleaned['restrictions'] = data.get('restrictions', None)
    
    # Write cleaned data
    with open(output_file, 'w') as f:
        json.dump(cleaned, f, indent=2)
    
    print(f"Cleaned protection backup saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean_protection_backup.py input.json output.json")
        sys.exit(1)
    
    clean_protection_backup(sys.argv[1], sys.argv[2])