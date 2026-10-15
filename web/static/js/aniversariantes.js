(function () {
  "use strict";
  const { h, api, avisar } = window.SIGMComum;
  const el = {
    mes: document.getElementById("mes"),
    busca: document.getElementById("busca"),
    lista: document.getElementById("lista"),
    hoje: document.getElementById("n-hoje"),
    totalMes: document.getElementById("n-mes"),
    rotuloMes: document.getElementById("rotulo-mes"),
  };

  async function carregar() {
    const params = new URLSearchParams({ mes: el.mes.value });
    if (el.busca.value.trim()) params.set("q", el.busca.value.trim());
    let r;
    try { r = await api("/api/aniversariantes?" + params); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar("Não foi possível carregar os aniversariantes.", true); return; }
    const d = r.dados;
    el.hoje.textContent = d.total_hoje;
    el.totalMes.textContent = d.total_mes;
    el.rotuloMes.textContent = "Aniversariantes de " + el.mes.options[el.mes.selectedIndex].text.toLowerCase();
    el.lista.replaceChildren();
    if (!d.itens.length) {
      el.lista.append(h("li", { class: "lista-vazia" }, "Nenhum aniversariante encontrado."));
      return;
    }
    for (const i of d.itens) {
      el.lista.append(h("li", { class: "cartao" + (i.hoje ? " cartao-hoje" : "") },
        h("span", { class: "cartao-dia" }, String(i.dia).padStart(2, "0")),
        h("span", { class: "cartao-corpo" },
          h("a", { class: "cartao-nome", href: "/membros?abrir=" + i.id }, i.nome || "-"),
          h("span", { class: "item-sub" },
            `${i.data} · completa ${i.idade} anos` + (i.contato ? " · " + i.contato : ""))),
        i.hoje && h("span", { class: "selo selo-aprovado" }, "Hoje")));
    }
  }

  el.mes.addEventListener("change", carregar);
  let t;
  el.busca.addEventListener("input", () => { clearTimeout(t); t = setTimeout(carregar, 250); });
  carregar();
})();
