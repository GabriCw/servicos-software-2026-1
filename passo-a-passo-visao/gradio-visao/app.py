import gradio as gr
import requests

def analisar_imagem(imagem_path):
    if imagem_path is None:
        return "Nenhuma imagem enviada."
    
    with open(imagem_path, "rb") as f:
        files = {"file": f}
        try:
            # Envia a imagem via REST para o backend de IA
            response = requests.post("http://api-visao:8081/analisar", files=files)
            if response.status_code == 200:
                dados = response.json()
                return f"Rótulo gerado pela IA: {dados.get('rotulo')}\nStatus BD: {dados.get('status_db')}"
            else:
                return f"Erro no servidor: {response.status_code}"
        except Exception as e:
            return f"Erro de comunicação: {str(e)}"

demo = gr.Interface(
    fn=analisar_imagem,
    inputs=gr.Image(type="filepath", label="Faça upload de uma imagem"),
    outputs=gr.Textbox(label="Resultado da IA e Banco de Dados"),
    title="👁️ Reconhecimento de Imagens"
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861)