"""A basic Lambda that returns its version"""
VERSION = '0.0.2'

def lambda_handler(_event, _context):
    return VERSION
