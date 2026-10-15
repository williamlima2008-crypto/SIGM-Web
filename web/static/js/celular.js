(function () {
  "use strict";
  const { h, api, avisar, confirmar } = window.SIGMComum;
  const $ = (id) => document.getElementById(id);
  let ativado = false;
  let ocupado = false;
  let alteracoes = [];
  let temporizador = null;

  function rotulo(campo) {
    const texto = campo.replace(/_/g, " ");
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  function atualizarBotoes() {
    $("btn-enviar").disabled = !ativado || ocupado;
    $("btn-buscar").disabled = !ativado || ocupado;
  }

  function desenhar(s) {
    ativado = !!s.ativado;
    ocupado = !!s.em_andamento;
    const selo = $("estado");
    selo.textContent = ativado ? "Integração ativa" : "Integração não ativada";
    selo.className = "selo " + (ativado ? "selo-aprovado" : "selo-pendente");
    $("aviso-inativo").hidden = ativado;
    const progresso = $("progresso");
    progresso.hidden = !s.em_andamento;
    progresso.textContent = s.mensagem || "";
    const resultado = $("resultado");
    const texto = s.erro || (s.resumo_texto ? s.resumo_texto + (s.concluido_em ? " (" + s.concluido_em + ")" : "") : "");
    resultado.textContent = texto;
    resultado.className = "celular-resultado" + (s.erro ? " celular-erro" : "");
    resultado.hidden = !texto || s.em_andamento;
    $("btn-enviar").textContent = s.em_andamento ? "Enviando..." : "Enviar dados ao Celular";
    atualizarBotoes();
  }

  async function carregar() {
    let r;
    try { r = await api("/api/celular"); } catch (e) { avisar(e.message, true); return null; }
    if (!r.ok) { avisar("Não foi possível carregar o estado do Celular.", true); return null; }
    desenhar(r.dados);
    return r.dados;
  }

  function acompanhar() {
    clearTimeout(temporizador);
    temporizador = setTimeout(async () => {
      const s = await carregar();
      if (s && s.em_andamento) acompanhar();
      else if (s && !s.erro && s.resumo_texto) avisar(s.resumo_texto);
      else if (s && s.erro) avisar(s.erro, true);
    }, 1000);
  }

  async function enviar() {
    const ok = await confirmar({
      titulo: "Enviar dados ao Celular",
      texto: "Os membros, as fotos e os dados da igreja que mudaram serão enviados ao Celular. Deseja continuar?",
      botao: "Enviar",
    });
    if (!ok) return;
    ocupado = true; atualizarBotoes();
    let r;
    try { r = await api("/api/celular/enviar", { method: "POST", json: {} }); }
    catch (e) { ocupado = false; atualizarBotoes(); avisar(e.message, true); return; }
    if (!r.ok) { ocupado = false; atualizarBotoes(); avisar(r.dados.mensagem || "Não foi possível iniciar o envio.", true); carregar(); return; }
    await carregar();
    acompanhar();
  }

  function cartao(alteracao) {
    const situacao = alteracao.situacao || {};
    const existe = situacao.existe !== false;
    const campos = Object.entries(situacao.campos || {});
    return h("article", { class: "celular-cartao" },
      h("h3", null, (alteracao.nome || "(sem nome)") + " – sugerido por " + (alteracao.criado_por || "-")),
      !existe && h("p", { class: "celular-erro" }, "Este membro não existe mais no SIGM. Rejeite a sugestão."),
      campos.map(([campo, v]) => h("p", { class: "celular-campo" },
        h("strong", null, rotulo(campo) + ": "),
        (v.atual || "-") + "  →  " + (v.depois || "-"),
        (v.antes || "") !== (v.atual || "") && h("span", { class: "celular-aviso" }, " (o dado mudou no SIGM depois da sugestão)"))),
      h("div", { class: "barra-botoes" },
        h("button", { type: "button", class: "btn btn-sucesso", disabled: !existe, onclick: () => responder(alteracao, true) }, "Aplicar no SIGM"),
        h("button", { type: "button", class: "btn btn-perigo", onclick: () => responder(alteracao, false) }, "Rejeitar")));
  }

  function desenharAlteracoes() {
    const lista = $("lista-alteracoes");
    lista.replaceChildren();
    if (!alteracoes.length) {
      lista.append(h("p", { class: "item-sub" }, "Nenhuma alteração aguardando."));
      return;
    }
    alteracoes.forEach((a) => lista.append(cartao(a)));
  }

  async function buscar() {
    ocupado = true; atualizarBotoes();
    $("btn-buscar").textContent = "Buscando...";
    try {
      const r = await api("/api/celular/alteracoes/buscar", { method: "POST", json: {} });
      if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível buscar as alterações.", true); return; }
      alteracoes = r.dados.alteracoes || [];
      desenharAlteracoes();
      avisar(alteracoes.length ? alteracoes.length + " alteração(ões) sugerida(s)." : "Nenhuma alteração aguardando.");
    } catch (e) { avisar(e.message, true); }
    finally { ocupado = false; $("btn-buscar").textContent = "Buscar alterações"; atualizarBotoes(); }
  }

  async function responder(alteracao, aplicar) {
    const nome = alteracao.nome || "este membro";
    const ok = await confirmar({
      titulo: aplicar ? "Aplicar alterações" : "Rejeitar sugestão",
      texto: aplicar ? "Aplicar as alterações sugeridas para " + nome + " no SIGM?"
                     : "Deseja mesmo rejeitar a sugestão para " + nome + "?",
      botao: aplicar ? "Aplicar" : "Rejeitar", perigo: !aplicar,
    });
    if (!ok) return;
    let r;
    try {
      r = await api("/api/celular/alteracoes/responder", { method: "POST", json: { id: alteracao.id, acao: aplicar ? "aplicar" : "rejeitar" } });
    } catch (e) { avisar(e.message, true); return; }
    avisar(r.dados.mensagem || (r.ok ? "Feito." : "Não foi possível concluir."), !r.ok);
    if (r.ok || r.status === 404) {
      alteracoes = alteracoes.filter((a) => a.id !== alteracao.id);
      desenharAlteracoes();
    }
  }

  $("btn-enviar").addEventListener("click", enviar);
  $("btn-buscar").addEventListener("click", buscar);
  carregar().then((s) => { if (s && s.em_andamento) acompanhar(); });
})();
