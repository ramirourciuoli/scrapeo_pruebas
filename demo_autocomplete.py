from flask import Flask, request, jsonify, render_template_string
from buscador_caba import sugerir_calles_caba  # <- ajustaremos el nombre de función si es distinto

app = Flask(__name__)

@app.get("/autocomplete/calles")
def autocomplete_calles():
    q = request.args.get("q", "")
    limit = int(request.args.get("limit", 10))
    return jsonify(sugerir_calles_caba(q, limit=limit))

@app.get("/demo")
def demo():
    html = """
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Demo Autocomplete Calles CABA</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 24px; }
        .box { max-width: 520px; }
        input { width: 100%; padding: 12px; font-size: 16px; }
        ul { list-style: none; padding: 0; margin: 6px 0 0 0; border: 1px solid #ddd; border-radius: 8px; }
        li { padding: 10px 12px; border-bottom: 1px solid #eee; cursor: pointer; }
        li:last-child { border-bottom: none; }
        li:hover { background: #f5f5f5; }
        .muted { color: #666; font-size: 12px; margin-top: 8px; }
      </style>
    </head>
    <body>
      <div class="box">
        <h2>Autocomplete de calles (solo CABA)</h2>
        <p class="muted">Escribí al menos 3 letras (ej: "more", "mitre", "corr").</p>

        <input id="calle" placeholder="Escribí una calle..." autocomplete="off" />
        <ul id="sugerencias" style="display:none;"></ul>

        <p class="muted" id="seleccion"></p>
      </div>

      <script>
        const input = document.getElementById("calle");
        const ul = document.getElementById("sugerencias");
        const sel = document.getElementById("seleccion");
        let timer = null;

        function hideList() {
          ul.style.display = "none";
          ul.innerHTML = "";
        }

        input.addEventListener("input", () => {
          const q = input.value.trim();

          clearTimeout(timer);
          timer = setTimeout(async () => {
            if (q.length < 3) { hideList(); return; }

            const res = await fetch(`/autocomplete/calles?q=${encodeURIComponent(q)}&limit=10`);
            const data = await res.json();

            ul.innerHTML = "";
            const items = data.sugerencias || [];

            if (items.length === 0) { hideList(); return; }

            items.forEach(item => {
              const li = document.createElement("li");
              li.textContent = item.label || item.nombre_calle || JSON.stringify(item);
              li.onclick = () => {
                input.value = li.textContent;
                sel.textContent = "Elegiste: " + li.textContent;
                hideList();
              };
              ul.appendChild(li);
            });

            ul.style.display = "block";
          }, 250);
        });

        document.addEventListener("click", (e) => {
          if (e.target !== input && !ul.contains(e.target)) hideList();
        });
      </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    # Puerto distinto para NO tocar tu app.py
    app.run(host="127.0.0.1", port=8001, debug=True)