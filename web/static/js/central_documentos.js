(function () {
  "use strict";
  const { h, api, avisar, formulario } = window.SIGMComum;
  const lista = document.getElementById("lista");
  const busca = document.getElementById("busca");
  const resumo = document.getElementById("resumo");
  const total = document.getElementById("n-total");

  async function carregar() {
    const q = busca.value.trim();
    let r;
    try { r = await api("/api/documentos-emitidos" + (q ? "?q=" + encodeURIComponent(q) : "")); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Não foi possível carregar os documentos.", true); return; }
    const d = r.dados;
    total.textContent = d.total;
    resumo.textContent = d.filtrado ? `${d.itens.length} encontrado(s)` : `Mostrando os ${d.itens.length} mais recentes`;
    lista.replaceChildren();
    if (!d.itens.length) { lista.append(h("li", { class: "lista-vazia" }, "Nenhum documento emitido encontrado.")); return; }
    for (const i of d.itens) {
      lista.append(h("li", { class: "cartao" },
        h("span", { class: "cartao-corpo" },
          h("strong", { class: "cartao-nome" }, i.titulo),
          h("span", { class: "item-sub" },
            [i.membro && ("Membro: " + i.membro), i.data, i.usuario && ("Por " + i.usuario)].filter(Boolean).join(" · "))),
        i.membro_id && h("a", { class: "btn btn-secundario btn-pequeno", href: "/membros?abrir=" + i.membro_id }, "Ficha"),
        i.disponivel
          ? h("a", { class: "btn btn-primario btn-pequeno", href: `/api/documentos-emitidos/${i.id}/arquivo`, target: "_blank", rel: "noopener" }, "Abrir")
          : h("span", { class: "item-sub" }, "Arquivo não encontrado"),
        h("button", { type: "button", class: "btn btn-perigo btn-pequeno", onclick: () => excluir(i) }, "Excluir")));
    }
  }
  async function excluir(i) {
    const campos = i.disponivel
      ? [{ nome: "fisico", tipo: "checkbox", valor: true, rotulo: "Apagar também o arquivo PDF",
           ajuda: "Libera espaço no computador. Desmarcado, só o registro sai da lista." }]
      : [];
    const v = await formulario({
      titulo: "Excluir documento", botao: "Excluir", campos,
      texto: `Excluir "${i.titulo}" do histórico? Esta ação não pode ser desfeita.`,
    });
    if (!v) return;
    let r;
    try { r = await api(`/api/documentos-emitidos/${i.id}/excluir`, { method: "POST", json: { fisico: !!v.fisico } }); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível excluir.", true); return; }
    avisar(r.dados.arquivo_apagado ? "Registro e PDF excluídos." : "Registro excluído.");
    carregar();
  }
  let t;
  busca.addEventListener("input", () => { clearTimeout(t); t = setTimeout(carregar, 250); });
  carregar();
})();
