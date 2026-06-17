"""IISP (Industrial Inspection Solutions Platform) entry point."""
import os
from server.factory import create_app

app = create_app()

if __name__ == '__main__':
    use_reloader = os.environ.get('PC_RELOAD', '').lower() in ('1', 'true', 'yes')
    port = int(os.environ.get('IISP_PORT', '5050'))
    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=use_reloader)
