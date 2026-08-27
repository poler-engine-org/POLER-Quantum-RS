import http.server
import socketserver
import json
import struct
import numpy as np
from pathlib import Path

PORT = 7890

class GraphHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/data':
            pqw_path = Path('/home/vitalij/Стільниця/POLER-Quantum-RS_repo/internet_master_state.pqw')
            if not pqw_path.exists():
                pqw_path = Path('/home/vitalij/Стільниця/POLER-Quantum-RS_repo/master_learned_state.pqw')
            
            raw = pqw_path.read_bytes()
            header = raw[:128]
            payload = raw[128:]
            
            bits = ''.join(f'{b:08b}' for b in payload)
            trits = []
            trit_map = {'00': -1, '01': 0, '10': 1, '11': 0}
            for i in range(0, len(bits), 2):
                trits.append(trit_map.get(bits[i:i+2], 0))
            
            nodes = []
            edges = []
            
            active = [i for i, t in enumerate(trits) if t != 0]
            for idx, a in enumerate(active):
                nodes.append({'id': a, 'label': f'Arc {a}', 'val': trits[a], 'group': 1 if trits[a] > 0 else 2})
                if idx > 0:
                    edges.append({'from': active[idx-1], 'to': a, 'weight': 1.0})
            
            data = {
                'd_pol': len(trits),
                'nnz': len(active),
                'active_nodes': active,
                'nodes': nodes,
                'edges': edges,
                'hex_preview': ' '.join(f'{b:02X}' for b in payload[:64])
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return
            
        elif self.path == '/' or self.path == '/index.html':
            html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>POLER Quantum Binary & Graph Visualizer</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body { background: #0d1117; color: #c9d1d9; font-family: monospace; margin: 0; padding: 20px; }
        #network { width: 100%; height: 500px; border: 1px solid #30363d; border-radius: 8px; background: #161b22; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        h2 { color: #58a6ff; margin-top: 0; }
        .badge { background: #238636; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        pre { background: #090c10; padding: 10px; border-radius: 6px; overflow-x: auto; color: #7ee787; }
    </style>
</head>
<body>
    <div class="card">
        <h2>⚛️ POLER Quantum: Граф Топологии LENS и Бинарная Дешифровка</h2>
        <p>Квантовый кристалл: <span class="badge" id="info">Загрузка...</span></p>
        <pre id="hexDump"></pre>
    </div>
    <div class="card">
        <h3>🕸️ Топологический Граф Фазовых Связей (Ker(P) / LENS)</h3>
        <div id="network"></div>
    </div>
    <script>
        fetch('/api/data')
            .then(res => res.json())
            .then(data => {
                document.getElementById('info').innerText = 'd_pol: ' + data.d_pol + ' | Активных дуг: ' + data.nnz;
                document.getElementById('hexDump').innerText = 'HEX Дамп L1 регистров:\n' + data.hex_preview;
                
                var nodes = new vis.DataSet(data.nodes.map(n => ({
                    id: n.id,
                    label: n.label + ' (' + (n.val > 0 ? '+1' : '-1') + ')',
                    color: n.val > 0 ? '#2ea043' : '#f85149',
                    font: { color: '#ffffff' }
                })));
                
                var edges = new vis.DataSet(data.edges.map(e => ({
                    from: e.from,
                    to: e.to,
                    color: '#58a6ff',
                    width: 2,
                    arrows: 'to'
                })));
                
                var container = document.getElementById('network');
                var network = new vis.Network(container, { nodes: nodes, edges: edges }, {
                    physics: { barnesHut: { springLength: 100 } }
                });
            });
    </script>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            return
            
        super().do_GET()

print(f'Starting Graph Visualizer Server on port {PORT}...')
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', PORT), GraphHandler) as httpd:
    httpd.serve_forever()
