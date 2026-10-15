/* Utilidades compartilhadas pelas telas simples (aniversariantes, relatórios). */
window.SIGMComum = (function () {
  "use strict";
  function h(tag, atributos, ...filhos) {
    const no = document.createElement(tag);
    for (const [chave, valor] of Object.entries(atributos || {})) {
      if (valor === null || valor === undefined || valor === false) continue;
      if (chave === "class") no.className = valor;
      else if (chave.startsWith("on")) no.addEventListener(chave.slice(2), valor);
      else no.setAttribute(chave, valor === true ? "" : valor);
    }
    for (const filho of filhos.flat()) {
      if (filho === null || filho === undefined || filho === false) continue;
      no.append(filho.nodeType ? filho : document.createTextNode(String(filho)));
    }
    return no;
  }

  async function api(caminho, opcoes = {}) {
    const config = { method: opcoes.method || "GET", headers: { "X-SIGM": "1" } };
    if (opcoes.json !== undefined) {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(opcoes.json);
    }
    let resposta;
    try {
      resposta = await fetch(caminho, config);
    } catch (e) {
      throw new Error("Não foi possível falar com o SIGM. Confira se ele está aberto.");
    }
    if (resposta.status === 401) { window.location.href = "/login"; throw new Error("Sessão expirada."); }
    const dados = await resposta.json().catch(() => ({}));
    return { ok: resposta.ok, status: resposta.status, dados };
  }

  const aviso = document.getElementById("aviso");
  let temporizador;
  function avisar(texto, erro) {
    aviso.textContent = texto;
    aviso.classList.toggle("erro-aviso", !!erro);
    aviso.hidden = false;
    clearTimeout(temporizador);
    temporizador = setTimeout(() => { aviso.hidden = true; }, erro ? 7000 : 4500);
  }

  const sair = document.getElementById("btn-sair");
  if (sair) sair.addEventListener("click", async () => {
    const ok = await confirmar({ titulo: "Sair do SIGM", texto: "Deseja encerrar a sua sessão?", botao: "Sair" });
    if (!ok) return;
    await api("/api/logout", { method: "POST", json: {} });
    window.location.href = "/login";
  });

  /* Diálogos criados na hora (não exigem marcação na página). */
  function abrirDialogo(montar) {
    return new Promise((resolver) => {
      const caixa = h("dialog", { class: "dialogo-dinamico" });
      let resultado = null;
      const fechar = (valor) => { resultado = valor; caixa.close(); };
      caixa.addEventListener("close", () => { caixa.remove(); resolver(resultado); });
      caixa.addEventListener("cancel", () => { resultado = null; });
      montar(caixa, fechar);
      document.body.append(caixa);
      caixa.showModal();
    });
  }

  function confirmar({ titulo, texto, botao = "Confirmar", perigo = false }) {
    return abrirDialogo((caixa, fechar) => {
      caixa.append(h("form", { method: "dialog", onsubmit: (e) => { e.preventDefault(); fechar(true); } },
        h("h2", null, titulo), texto && h("p", null, texto),
        h("div", { class: "dialogo-botoes" },
          h("button", { type: "button", class: "btn btn-secundario", onclick: () => fechar(false) }, "Cancelar"),
          h("button", { type: "submit", class: "btn " + (perigo ? "btn-perigo" : "btn-primario") }, botao))));
    }).then((v) => v === true);
  }

  /* campos: [{nome, rotulo, tipo?, valor?, opcoes?:[[valor,rotulo]], requerido?, ajuda?}] */
  function formulario({ titulo, texto, campos, botao = "Salvar", validar }) {
    return abrirDialogo((caixa, fechar) => {
      const entradas = {};
      const erro = h("p", { class: "erro", role: "alert", hidden: true });
      const blocos = campos.map((c) => {
        let entrada;
        if (c.opcoes) {
          entrada = h("select", { name: c.nome }, c.opcoes.map(([v, r]) => h("option", { value: v }, r)));
          entrada.value = c.valor ?? c.opcoes[0][0];
        } else if (c.tipo === "checkbox") {
          entrada = h("input", { type: "checkbox", name: c.nome });
          entrada.checked = !!c.valor;
        } else {
          entrada = h("input", { type: c.tipo || "text", name: c.nome, maxlength: "120",
            autocomplete: c.tipo === "password" ? "new-password" : "off", autocapitalize: "none" });
          entrada.value = c.valor || "";
        }
        entradas[c.nome] = entrada;
        return h("label", { class: c.tipo === "checkbox" ? "linha-check" : null },
          c.tipo === "checkbox" ? [entrada, c.rotulo] : [c.rotulo, entrada],
          c.ajuda && h("span", { class: "item-sub" }, c.ajuda));
      });
      const valores = () => Object.fromEntries(campos.map((c) => {
        const e = entradas[c.nome];
        return [c.nome, c.tipo === "checkbox" ? e.checked : e.value];
      }));
      caixa.append(h("form", { method: "dialog", class: "dialogo-form", onsubmit: (e) => {
        e.preventDefault();
        const v = valores();
        const problema = validar && validar(v);
        if (problema) { erro.textContent = problema; erro.hidden = false; return; }
        fechar(v);
      } },
        h("h2", null, titulo), texto && h("p", null, texto), ...blocos, erro,
        h("div", { class: "dialogo-botoes" },
          h("button", { type: "button", class: "btn btn-secundario", onclick: () => fechar(null) }, "Cancelar"),
          h("button", { type: "submit", class: "btn btn-primario" }, botao))));
      setTimeout(() => { const p = caixa.querySelector("input,select"); if (p) p.focus(); }, 0);
    });
  }

  return { h, api, avisar, confirmar, formulario };
})();
