"""
WSGI entry point for the application.
This file is needed for some hosting platforms that look for a wsgi.py file.
"""

from app import app

# This allows the application to be imported as 'wsgi'
# For platforms that look for application or app variables
application = app

if __name__ == '__main__':
    app.run() 