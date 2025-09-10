INPUT_SCHEMA = {
    'config': {
        'type': str,
        'required': True,
    },
    'dataset_url': {
        'type': str,
        'required': True,
    },
    'job_id': {
        'type': str,
        'required': True,
    },
    'webhook_url': {
        'type': str,
        'required': True,
    },
    'control_url': {
        'type': str,
        'required': False,
    }
}
