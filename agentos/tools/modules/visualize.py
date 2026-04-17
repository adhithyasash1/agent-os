import json
import os
import uuid
from ..core import tool

@tool(
    name="render_page",
    description="Generate a rich Apache ECharts HTML visualization file from raw data metrics.",
    args_schema={
        "type": "object",
        "properties": {
            "chart_type": {"type": "string", "description": "e.g. line, bar, pie, radar"},
            "title": {"type": "string", "description": "Title of the chart"},
            "data": {"type": "array", "description": "array of data points"}
        },
        "required": ["chart_type", "title", "data"]
    },
    profiles=["full"]
)
async def _render_page(args: dict, ctx: dict) -> dict:
    chart_type = (args or {}).get("chart_type", "bar")
    title = (args or {}).get("title", "Data Visualization")
    data = (args or {}).get("data", [])
    
    file_id = str(uuid.uuid4())[:8]
    filepath = f"data/exports/{file_id}.html"

    # Minimal ECharts HTML Template injecting user data natively
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #fafafa; margin: 0; padding: 20px; }}
            #main {{ width: 100%; height: 600px; background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 20px; }}
        </style>
    </head>
    <body>
        <div id="main"></div>
        <script>
            var chartDom = document.getElementById('main');
            var myChart = echarts.init(chartDom);
            var option;

            option = {{
                title: {{ text: '{title}' }},
                tooltip: {{}},
                xAxis: {{ type: 'category', data: {json.dumps([item.get("name", f"Point {{i}}") for i, item in enumerate(data) if isinstance(item, dict)])} }},
                yAxis: {{ type: 'value' }},
                series: [{{
                    data: {json.dumps([item.get("value", 0) for item in data if isinstance(item, dict)])},
                    type: '{chart_type}'
                }}]
            }};
            
            // Adjust pie option loosely if chart_type is pie
            if ('{chart_type}' === 'pie') {{
                option.xAxis = null;
                option.yAxis = null;
                option.series = [{{
                    type: 'pie',
                    radius: '50%',
                    data: {json.dumps(data)}
                }}];
            }}

            option && myChart.setOption(option);
            window.addEventListener('resize', myChart.resize);
        </script>
    </body>
    </html>
    """

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "status": "ok", 
        "output": f"Chart generated successfully! Tell the user to view it here: http://localhost:8000/static/{file_id}.html"
    }
