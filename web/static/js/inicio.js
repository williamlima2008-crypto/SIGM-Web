(function () {
  "use strict";
  const { h, api, avisar } = window.SIGMComum;

  function preencher(id, itens, vazio) {
    const ul = document.getElementById(id);
    ul.replaceChildren();
    if (!itens.length) { ul.append(h("li", { class: "lista-vazia" }, vazio)); return; }
    for (const i of itens) ul.append(i);
  }

  async function carregar() {
    let r;
    try { r = await api("/api/painel"); } catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Não foi possível carregar o painel.", true); return; }
    const d = r.dados;
    for (const [chave, valor] of Object.entries(d.indicadores)) {
      const no = document.querySelector(`[data-ind="${chave}"]`);
      if (no) no.textContent = valor;
    }
    preencher("b-membros", d.ultimos_membros.map((m) => h("li", {},
      h("a", { href: "/membros?abrir=" + m.id }, m.nome || "-"), h("span", { class: "item-sub" }, m.status || ""))),
      "Nenhum membro cadastrado.");
    preencher("b-aniversarios", d.aniversariantes.map((a) => h("li", {},
      h("a", { href: "/membros?abrir=" + a.id }, a.nome || "-"),
      h("span", { class: "item-sub" }, a.data + (a.dias === 0 ? " · hoje" : ` · em ${a.dias} dia(s)`)))),
      "Nenhum aniversário encontrado.");
    preencher("b-atividades", d.atividades.map((a) => h("li", {},
      h("span", {}, a.texto), h("span", { class: "item-sub" }, a.data))),
      "Nenhuma atividade recente.");
    const b = d.backup;
    preencher("b-backup", b.existe
      ? [h("li", {}, b.arquivo), h("li", {}, h("span", { class: "item-sub" }, `${b.data} · ${b.tamanho}`))]
      : [], "Nenhum backup encontrado.");
  }
  carregar();
})();
