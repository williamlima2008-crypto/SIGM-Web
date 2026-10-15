(function () {
  "use strict";
  const { api, avisar } = window.SIGMComum;
  const form = document.getElementById("form-igreja");
  const botaoSalvar = document.getElementById("btn-salvar-igreja");
  const seletor = document.getElementById("arquivo-imagem");
  let original = {};
  let tipoEscolhido = null;

  function preencher(campos) {
    original = campos;
    for (const entrada of form.querySelectorAll("input[name]")) {
      entrada.value = campos[entrada.name] || "";
    }
  }

  function atualizarImagens(imagens) {
    for (const bloco of document.querySelectorAll(".imagem-igreja")) {
      const info = imagens[bloco.dataset.tipo] || {};
      const img = bloco.querySelector("img");
      const vazio = bloco.querySelector(".imagem-vazia");
      if (info.tem) {
        img.src = `/igreja/imagem/${bloco.dataset.tipo}?v=${info.versao}&t=${Date.now()}`;
        img.hidden = false; vazio.hidden = true;
      } else {
        img.hidden = true; img.removeAttribute("src"); vazio.hidden = false;
      }
      bloco.querySelector('[data-acao="remover"]').hidden = !info.tem;
    }
  }

  async function carregar() {
    const r = await api("/api/igreja");
    if (!r.ok) { avisar("Não foi possível carregar os dados da igreja.", true); return; }
    preencher(r.dados.campos);
    atualizarImagens(r.dados.imagens);
  }

  // abas
  const botoesAba = document.querySelectorAll("#igreja-abas button");
  function abrirAba(nome) {
    for (const b of botoesAba) b.setAttribute("aria-selected", String(b.dataset.aba === nome));
    for (const p of document.querySelectorAll(".igreja-painel")) p.hidden = p.dataset.painel !== nome;
  }
  for (const b of botoesAba) b.addEventListener("click", () => abrirAba(b.dataset.aba));

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const enviar = {};
    for (const entrada of form.querySelectorAll("input[name]")) enviar[entrada.name] = entrada.value;
    for (const entrada of form.querySelectorAll("input[required]")) {
      if (!entrada.value.trim()) {
        const painel = entrada.closest(".igreja-painel").dataset.painel;
        abrirAba(painel); entrada.focus();
        avisar("Preencha os campos obrigatórios (*).", true);
        return;
      }
    }
    botaoSalvar.disabled = true;
    try {
      const r = await api("/api/igreja", { method: "PUT", json: enviar });
      if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível salvar.", true); return; }
      preencher(r.dados.campos);
      avisar(r.dados.mensagem);
    } catch (e) { avisar(e.message, true); }
    finally { botaoSalvar.disabled = false; }
  });

  document.getElementById("btn-descartar-igreja").addEventListener("click", () => {
    preencher(original); avisar("Alterações descartadas.");
  });

  // imagens
  for (const bloco of document.querySelectorAll(".imagem-igreja")) {
    bloco.querySelector('[data-acao="trocar"]').addEventListener("click", () => {
      tipoEscolhido = bloco.dataset.tipo; seletor.value = ""; seletor.click();
    });
    bloco.querySelector('[data-acao="remover"]').addEventListener("click", async () => {
      if (!window.confirm("Remover esta imagem?")) return;
      const r = await api(`/api/igreja/imagem/${bloco.dataset.tipo}`, { method: "DELETE", json: {} });
      avisar(r.dados.mensagem || "Não foi possível remover.", !r.ok);
      if (r.ok) carregar();
    });
  }
  seletor.addEventListener("change", async () => {
    const arquivo = seletor.files[0];
    if (!arquivo || !tipoEscolhido) return;
    const dados = new FormData();
    dados.append("arquivo", arquivo);
    try {
      const resposta = await fetch(`/api/igreja/imagem/${tipoEscolhido}`, {
        method: "POST", headers: { "X-SIGM": "1" }, body: dados,
      });
      const corpo = await resposta.json().catch(() => ({}));
      avisar(corpo.mensagem || (resposta.ok ? "Imagem salva." : "Não foi possível enviar."), !resposta.ok);
      if (resposta.ok) carregar();
    } catch (e) { avisar("Não foi possível enviar a imagem.", true); }
  });

  carregar();
})();
