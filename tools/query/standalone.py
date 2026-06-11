"""独立部署入口：python -m tools.query.standalone"""
from __future__ import annotations

import os

from tools.query.standalone_app import create_standalone_app

app = create_standalone_app()


def main():
    port = int(os.environ.get('QUERY_TOOL_PORT', '6021'))
    host = os.environ.get('QUERY_TOOL_HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=os.environ.get('QUERY_TOOL_DEBUG') == '1')


if __name__ == '__main__':
    main()
