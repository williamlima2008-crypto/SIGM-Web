(function () {
  "use strict";
  const { api, avisar, confirmar, formulario } = window.SIGMComum;
  const $ = (id) => document.getElementById(id);
  let estado = null;

  async function copiar(texto, mensagem) {
    try { await navigator.clipboard.writeText(texto); avisar(mensagem); }
    catch (e) { await formulario({ titulo: "Copie manualmente", botao: "Fechar", campos: [{ nome: "t", rotulo: "Texto", valor: texto }] }); }
  }

  function desenhar(s) {
    estado = s;
    const selo = $("estado");
    selo.textContent = s.estado;
    selo.className = "selo " + (s.ativado ? "selo-aprovado" : s.configurado ? "selo-pendente" : "selo-rejeitado");
    $("sincronizacao").textContent = s.ultima_sincronizacao ? "Última sincronização: " + s.ultima_sincronizacao : "";
    $("servidor").textContent = s.servidor;
    $("identificador").textContent = s.identificador || "Não gerado";
    $("chave").textContent = s.chave_mascarada || "Não gerada";
    $("link").textContent = s.link || "Não gerado";
    $("btn-copiar-link").disabled = !s.link;
    $("btn-qr").disabled = !s.ativado;
    $("btn-qr").textContent = s.qrcode.existe ? "Gerar novo QR Code" : "Gerar QR Code";
    const img = $("qr");
    if (s.qrcode.existe) { img.src = "/api/online/qrcode.png?v=" + s.qrcode.versao + "&t=" + Date.now(); img.hidden = false; $("qr-vazio").hidden = true; }
    else { img.hidden = true; img.removeAttribute("src"); $("qr-vazio").hidden = false; }
    $("btn-baixar-qr").hidden = !s.qrcode.existe;
    $("acoes-admin").hidden = !s.admin;
    $("aviso-admin").hidden = s.admin;
    $("btn-ativar").hidden = s.ativado;
    $("btn-testar").hidden = !s.configurado;
    $("btn-chave").hidden = !s.tem_chave;
  }

  async function carregar() {
    let r;
    try { r = await api("/api/online"); } catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Não foi possível carregar a configuração online.", true); return; }
    desenhar(r.dados);
  }

  async function chamar(caminho, botao, textoEspera) {
    const original = botao.textContent;
    botao.disabled = true; botao.textContent = textoEspera;
    try {
      const r = await api(caminho, { method: "POST", json: {} });
      avisar(r.dados.mensagem || (r.ok ? "Feito." : "Não foi possível concluir."), !r.ok);
      if (r.ok) desenhar(r.dados); else carregar();
    } catch (e) { avisar(e.message, true); }
    finally { botao.disabled = false; botao.textContent = original; }
  }

  $("btn-ativar").addEventListener("click", async () => {
    const ok = await confirmar({ titulo: "Ativar integração online?", texto: "Será criada a identidade online desta instalação e a integração será ativada no SIGM Online.", botao: "Ativar" });
    if (ok) chamar("/api/online/ativar", $("btn-ativar"), "Ativando...");
  });
  $("btn-testar").addEventListener("click", () => chamar("/api/online/testar", $("btn-testar"), "Testando..."));
  $("btn-qr").addEventListener("click", () => chamar("/api/online/qrcode", $("btn-qr"), "Gerando..."));
  $("btn-copiar-link").addEventListener("click", () => estado && estado.link && copiar(estado.link, "Link copiado."));
  $("btn-chave").addEventListener("click", async () => {
    const r = await api("/api/online/chave", { method: "POST", json: {} });
    if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível obter a chave.", true); return; }
    await copiar(r.dados.chave, "Chave copiada. Não compartilhe com ninguém.");
  });
  carregar();
})();
