from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


TERMOS_SECRETOS_URL = (
    "chave",
    "chave_sincronizacao",
    "password",
    "senha",
    "secret",
    "token",
)


class QRCodeIgrejaErro(Exception):
    pass


def validar_url_qrcode(url):
    texto = str(url or "").strip()
    if not texto:
        raise QRCodeIgrejaErro("Informe primeiro a URL publica do formulario.")

    partes = urlsplit(texto)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise QRCodeIgrejaErro("Informe uma URL publica valida para o formulario.")

    texto_minusculo = texto.lower()
    parametros = parse_qsl(partes.query, keep_blank_values=True)
    chaves_parametros = {chave.lower() for chave, _valor in parametros}
    if any(termo in texto_minusculo for termo in TERMOS_SECRETOS_URL):
        raise QRCodeIgrejaErro("A URL do QR Code nao pode conter segredo ou token.")
    if any(chave in TERMOS_SECRETOS_URL for chave in chaves_parametros):
        raise QRCodeIgrejaErro("A URL do QR Code nao pode conter segredo ou token.")

    return texto


def gerar_qrcode_igreja(url, caminho_destino):
    url = validar_url_qrcode(url)
    destino = Path(caminho_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        import qrcode
    except ImportError as erro:
        raise QRCodeIgrejaErro(
            "A biblioteca qrcode[pil] nao esta instalada."
        ) from erro

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    imagem = qr.make_image(fill_color="black", back_color="white")
    imagem.save(destino)
    return str(destino)
