"""A basic Lambda that returns its version"""
__version__ = '0.0.1'

def lambda_handler(_event, _context):
    return __version__
