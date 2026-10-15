(function () {
  "use strict";
  const { h, api, avisar, confirmar } = window.SIGMComum;
  const lista = document.getElementById("lista");
  const resumo = document.getElementById("resumo");
  const criar = document.getElementById("btn-criar");

  async function restaurar(b) {
    const ok = await confirmar({
      titulo: "Restaurar este backup?",
      texto: `${b.nome}\n\nOs dados atuais (banco, fotos, arquivos e documentos) serão substituídos pelos do backup. Antes disso o SIGM guarda um backup do estado atual.`,
      botao: "Restaurar", perigo: true,
    });
    if (!ok) return;
    let r;
    try { r = await api(`/api/backup/${encodeURIComponent(b.nome)}/restaurar`, { method: "POST", json: { confirmar: true } }); }
    catch (e) { avisar(e.message, true); return; }
    avisar(r.dados.mensagem || "Não foi possível restaurar.", !r.ok);
    if (r.ok) carregar();
  }

  async function carregar() {
    let r;
    try { r = await api("/api/backup"); } catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Não foi possível carregar os backups.", true); return; }
    resumo.textContent = r.dados.itens.length ? r.dados.itens.length + " backup(s)." : "";
    lista.replaceChildren();
    if (!r.dados.itens.length) { lista.append(h("li", { class: "lista-vazia" }, "Nenhum backup encontrado.")); return; }
    for (const b of r.dados.itens) {
      lista.append(h("li", { class: "cartao" },
        h("span", { class: "cartao-corpo" }, h("strong", { class: "cartao-nome" }, b.nome),
          h("span", { class: "item-sub" }, `${b.data} · ${b.tamanho}`)),
        r.dados.admin && h("span", { class: "cartao-acoes" },
          h("a", { class: "btn btn-secundario btn-pequeno", href: `/api/backup/${encodeURIComponent(b.nome)}/arquivo` }, "Baixar"),
          h("button", { type: "button", class: "btn btn-perigo btn-pequeno", onclick: () => restaurar(b) }, "Restaurar"))));
    }
  }

  criar.addEventListener("click", async () => {
    criar.disabled = true; criar.textContent = "Criando...";
    try {
      const r = await api("/api/backup", { method: "POST", json: {} });
      avisar(r.dados.mensagem || "Não foi possível criar o backup.", !r.ok);
      if (r.ok) carregar();
    } catch (e) { avisar(e.message, true); }
    finally { criar.disabled = false; criar.textContent = "Criar backup agora"; }
  });
  carregar();
})();
