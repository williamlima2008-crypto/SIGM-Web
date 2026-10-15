(function () {
  "use strict";

  const ROTULOS = window.SIGM.rotulos;
  const SECOES = window.SIGM.secoes;
  const NOMES_STATUS = {
    pendente: "Pendente", aprovado: "Aprovado",
    rejeitado: "Rejeitado", duplicado: "Duplicado",
  };
  const CAMPOS_COMPARACAO = [
    "nome", "cpf", "rg", "data_nascimento", "celular", "telefone",
    "email", "endereco", "cidade", "nome_mae",
  ];

  const estado = { status: "", busca: "", itens: [], selecionado: null, detalhe: null, editando: false };
  const el = {
    lista: document.getElementById("lista"),
    busca: document.getElementById("busca"),
    abas: document.getElementById("abas"),
    vazio: document.getElementById("detalhe-vazio"),
    conteudo: document.getElementById("detalhe-conteudo"),
    painel: document.getElementById("detalhe"),
    sincronizar: document.getElementById("btn-sincronizar"),
    arquivo: document.getElementById("arquivo-json"),
    sair: document.getElementById("btn-sair"),
    aviso: document.getElementById("aviso"),
  };

  /* ---------- utilidades ---------- */
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
    if (opcoes.form) config.body = opcoes.form;
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

  let temporizadorAviso;
  function avisar(texto, erro) {
    el.aviso.textContent = texto;
    el.aviso.classList.toggle("erro-aviso", !!erro);
    el.aviso.hidden = false;
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => { el.aviso.hidden = true; }, erro ? 7000 : 4500);
  }

  function formatarData(texto) {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(texto || "");
    if (!m) return texto || "";
    return `${m[3]}/${m[2]}/${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
  }

  function normalizar(valor) {
    return String(valor || "").toLowerCase().normalize("NFD")
      .replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");
  }

  /* ---------- diálogo ---------- */
  const dlg = {
    caixa: document.getElementById("dialogo"),
    form: document.getElementById("dialogo-form"),
    titulo: document.getElementById("dialogo-titulo"),
    texto: document.getElementById("dialogo-texto"),
    campo: document.getElementById("dialogo-campo"),
    rotulo: document.getElementById("dialogo-rotulo"),
    entrada: document.getElementById("dialogo-entrada"),
    ok: document.getElementById("dialogo-ok"),
    cancelar: document.getElementById("dialogo-cancelar"),
  };

  function perguntar({ titulo, texto, botao = "Confirmar", perigo = false, rotulo = null }) {
    return new Promise((resolver) => {
      dlg.titulo.textContent = titulo;
      dlg.texto.textContent = texto || "";
      dlg.texto.hidden = !texto;
      dlg.campo.hidden = !rotulo;
      dlg.rotulo.textContent = rotulo || "";
      dlg.entrada.value = "";
      dlg.ok.textContent = botao;
      dlg.ok.className = "btn " + (perigo ? "btn-perigo" : "btn-primario");
      let resultado = null;
      const fechar = () => {
        dlg.caixa.close();
        dlg.form.removeEventListener("submit", enviar);
        dlg.cancelar.removeEventListener("click", cancelar);
        dlg.caixa.removeEventListener("cancel", cancelar);
        resolver(resultado);
      };
      const enviar = (e) => { e.preventDefault(); resultado = rotulo ? dlg.entrada.value.trim() : true; fechar(); };
      const cancelar = (e) => { if (e) e.preventDefault(); resultado = null; fechar(); };
      dlg.form.addEventListener("submit", enviar);
      dlg.cancelar.addEventListener("click", cancelar);
      dlg.caixa.addEventListener("cancel", cancelar);
      dlg.caixa.showModal();
      (rotulo ? dlg.entrada : dlg.ok).focus();
    });
  }

  /* ---------- lista ---------- */
  async function carregarLista(manterSelecao = true) {
    const params = new URLSearchParams();
    if (estado.status) params.set("status", estado.status);
    if (estado.busca) params.set("q", estado.busca);
    const { ok, dados } = await api("/api/pre-cadastros?" + params);
    if (!ok) { avisar(dados.erro || "Não foi possível carregar a lista.", true); return; }
    estado.itens = dados.itens;
    for (const no of document.querySelectorAll(".n[data-n]")) {
      const valor = dados.contagem[no.dataset.n];
      no.textContent = valor ? `(${valor})` : "";
    }
    desenharLista();
    atualizarLote();
  }

  const PLURAIS = { aprovado: "aprovados", rejeitado: "rejeitados", duplicado: "duplicados" };
  function atualizarLote() {
    const bloco = document.getElementById("limpeza-lote");
    const plural = PLURAIS[estado.status];
    const n = estado.itens.length;
    bloco.hidden = !(plural && n && !estado.busca);
    if (!bloco.hidden) document.getElementById("btn-excluir-lote").textContent = `Excluir todos os ${plural} (${n})`;
  }

  async function excluirLote() {
    const plural = PLURAIS[estado.status];
    if (!plural) return;
    const confirmado = await perguntar({
      titulo: "Excluir em lote",
      texto: `Excluir definitivamente TODOS os pré-cadastros ${plural} (${estado.itens.length})?\n\nEsta ação não pode ser desfeita. Membros já cadastrados não são apagados e os pendentes não são afetados.`,
      botao: "Excluir todos", perigo: true,
    });
    if (!confirmado) return;
    const r = await api("/api/pre-cadastros/excluir-lote", { method: "POST", json: { status: estado.status } });
    if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível excluir.", true); return; }
    estado.selecionado = null; estado.detalhe = null;
    el.conteudo.hidden = true; el.vazio.hidden = false;
    avisar(r.dados.mensagem);
    await carregarLista();
  }
  document.getElementById("btn-excluir-lote").addEventListener("click", excluirLote);

  function desenharLista() {
    el.lista.replaceChildren();
    if (!estado.itens.length) {
      el.lista.append(h("li", { class: "lista-vazia" },
        estado.busca || estado.status
          ? "Nenhum pré-cadastro encontrado com esse filtro."
          : "Nenhum pré-cadastro ainda. Use Sincronizar para buscar os formulários online ou Importar JSON."));
      return;
    }
    for (const item of estado.itens) {
      const botao = h("button", {
        type: "button", class: "item", "data-status": item.status,
        "aria-current": item.id === estado.selecionado ? "true" : "false",
        onclick: () => abrirDetalhe(item.id),
      },
        h("span", { class: "regua" }),
        h("span", { class: "item-corpo" },
          h("span", { class: "item-nome", style: "display:block" }, item.nome || "(sem nome)"),
          h("span", { class: "item-sub" },
            [item.cpf, item.celular].filter(Boolean).join(" · ") || "Sem CPF ou celular")),
        h("span", { class: "item-lado" },
          h("span", { class: "selo selo-" + item.status }, NOMES_STATUS[item.status] || item.status),
          h("span", { style: "display:block;margin-top:2px" }, formatarData(item.recebido_em).slice(0, 10))),
      );
      el.lista.append(h("li", null, botao));
    }
  }

  /* ---------- detalhe ---------- */
  async function abrirDetalhe(id) {
    estado.selecionado = id;
    estado.editando = false;
    desenharLista();
    const { ok, dados } = await api("/api/pre-cadastros/" + id);
    if (!ok) { avisar(dados.erro || "Não foi possível abrir o pré-cadastro.", true); return; }
    estado.detalhe = dados;
    desenharDetalhe();
    document.body.classList.add("detalhe-aberto");
    el.painel.scrollTop = 0;
  }

  function fecharDetalheMobile() {
    document.body.classList.remove("detalhe-aberto");
  }

  function desenharDetalhe() {
    const d = estado.detalhe;
    el.vazio.hidden = true;
    el.conteudo.hidden = false;
    el.conteudo.replaceChildren();
    if (estado.editando) { desenharEdicao(d); return; }

    const pendente = d.status === "pendente";
    const nome = d.campos.nome || "(sem nome)";
    const foto = d.tem_foto
      ? h("img", { class: "foto", src: `/api/pre-cadastros/${d.id}/foto`, alt: "Foto de " + nome })
      : h("div", { class: "foto foto-vazia" }, "Sem foto");

    const topo = h("div", { class: "det-topo" }, foto,
      h("div", { class: "det-id" },
        h("h2", null, nome),
        h("div", { class: "det-meta" },
          h("span", { class: "selo selo-" + d.status }, NOMES_STATUS[d.status] || d.status),
          d.tecnico.recebido_em && h("span", null, "Recebido em " + formatarData(d.tecnico.recebido_em)),
          d.tecnico.origem && h("span", null, "Origem: " + d.tecnico.origem))));

    const acoes = h("div", { class: "acoes" });
    if (pendente) {
      acoes.append(
        h("button", { type: "button", class: "btn btn-sucesso", onclick: aprovar }, "Aprovar e cadastrar"),
      );
      if (d.total_candidatos > 0) {
        acoes.append(h("button", {
          type: "button", class: "btn btn-aviso",
          onclick: () => {
            if (d.candidatos.length === 1) atualizarExistente(d.candidatos[0]);
            else document.getElementById("comparar").scrollIntoView({ behavior: "smooth", block: "start" });
          },
        }, "Atualizar cadastro existente"));
      }
      acoes.append(
        h("button", { type: "button", class: "btn btn-secundario", onclick: () => { estado.editando = true; desenharDetalhe(); } }, "Editar dados"),
        h("button", { type: "button", class: "btn btn-perigo", onclick: rejeitar }, "Rejeitar"),
      );
    }
    acoes.append(h("button", { type: "button", class: "btn btn-perigo", onclick: excluir }, "Excluir"));

    const faltam = d.faltantes.length;
    let situacao = null;
    if (d.status === "aprovado") {
      situacao = h("p", { class: "situacao situacao-ok" },
        `Aprovado${d.tecnico.membro_id_aprovado ? " — membro nº " + d.tecnico.membro_id_aprovado : ""}` +
        (d.tecnico.usuario_revisor ? ` por ${d.tecnico.usuario_revisor}` : "") +
        (d.tecnico.revisado_em ? ` em ${formatarData(d.tecnico.revisado_em)}` : "") + ".");
    } else if (d.status === "rejeitado") {
      situacao = h("p", { class: "situacao situacao-rej" },
        "Rejeitado" + (d.tecnico.motivo_rejeicao ? `: ${d.tecnico.motivo_rejeicao}` : "."));
    } else if (d.status === "duplicado") {
      situacao = h("p", { class: "situacao situacao-rej" },
        "Marcado como duplicado" + (d.tecnico.duplicidade_membro_id ? ` do membro nº ${d.tecnico.duplicidade_membro_id}.` : "."));
    } else {
      situacao = h("p", { class: "situacao " + (faltam ? "situacao-falta" : "situacao-ok") },
        faltam ? `Faltam ${faltam} ${faltam === 1 ? "campo" : "campos"}. Você pode completar depois da aprovação.`
               : "Todos os campos foram preenchidos.");
    }

    el.conteudo.append(
      h("button", { type: "button", class: "btn btn-fantasma voltar", onclick: fecharDetalheMobile }, "Voltar para a lista"),
      topo, acoes, situacao,
    );

    if (pendente && d.total_candidatos > 0) el.conteudo.append(blocoComparacao(d));

    const faltantes = new Set(d.faltantes);
    for (const [titulo, campos] of SECOES) {
      const lista = h("dl", { class: "dados" });
      for (const campo of campos) {
        const valor = d.campos[campo];
        lista.append(h("div", { class: "dado" + (faltantes.has(campo) ? " falta" : "") + (campo === "observacoes" ? " largo" : "") },
          h("dt", null, ROTULOS[campo] || campo),
          h("dd", null, valor || "Não preenchido")));
      }
      el.conteudo.append(h("section", { class: "secao" }, h("h3", null, titulo), lista));
    }
  }

  function blocoComparacao(d) {
    const bloco = h("section", { class: "comparar", id: "comparar" },
      h("div", { class: "comparar-cab" },
        h("h3", null, d.total_candidatos === 1
          ? "Já existe um membro com o mesmo CPF e RG"
          : `Já existem ${d.total_candidatos} membros com o mesmo CPF e RG`),
        h("p", null, "Confira os dados lado a lado. Atualizar usa os dados novos nos campos preenchidos e mantém o que já existe nos campos vazios.")));

    for (const c of d.candidatos) {
      const linhas = [];
      for (const campo of CAMPOS_COMPARACAO) {
        const novo = d.campos[campo] || "";
        const atual = (c.membro && c.membro[campo]) || "";
        if (!novo && !atual) continue;
        const igual = novo && atual && normalizar(novo) === normalizar(atual);
        const diferente = novo && atual && !igual;
        const classe = igual ? "igual" : (novo && normalizar(novo) !== normalizar(atual) ? "diferente" : "");
        linhas.push(h("tr", { class: classe },
          h("th", { scope: "row" }, ROTULOS[campo] || campo),
          h("td", { class: "novo" }, novo || "—", diferente && h("span", { class: "marca marca-dif" }, "vai substituir")),
          h("td", null, atual || "—", igual && h("span", { class: "marca" }, "igual"))));
      }
      bloco.append(h("div", { class: "candidato" },
        h("div", { class: "cand-topo" },
          h("div", null,
            h("div", { class: "cand-nome" }, `${c.nome || "Membro"} (nº ${c.membro_id})`),
            h("div", { class: "cand-motivos" }, (c.motivos || []).join(", "))),
          h("span", { class: "selo " + (c.nivel === "alto" ? "selo-rejeitado" : "selo-pendente") },
            "Mesmo CPF e RG")),
        h("table", { class: "tabela-comp" },
          h("thead", null, h("tr", null, h("th", null, ""), h("th", null, "Pré-cadastro"), h("th", null, "Já no SIGM"))),
          h("tbody", null, linhas)),
        h("div", { class: "cand-botoes" },
          h("button", { type: "button", class: "btn btn-aviso", onclick: () => atualizarExistente(c) }, "Atualizar este cadastro"))));
    }
    return bloco;
  }

  /* ---------- ações ---------- */
  async function executar(botao, tarefa) {
    const todos = document.querySelectorAll(".acoes .btn, .cand-botoes .btn");
    todos.forEach((b) => (b.disabled = true));
    try { await tarefa(); } finally { todos.forEach((b) => (b.disabled = false)); }
  }

  async function depoisDeAcao(mensagem) {
    avisar(mensagem);
    await carregarLista();
    await abrirDetalhe(estado.detalhe.id);
  }

  async function aprovar() {
    const d = estado.detalhe;
    const faltam = d.faltantes.length;
    const confirmado = await perguntar({
      titulo: "Aprovar e cadastrar",
      texto: (faltam ? `Ainda faltam ${faltam} ${faltam === 1 ? "campo" : "campos"}; você poderá completar depois.\n\n` : "") +
        (d.total_candidatos > 0 ? "Atenção: já existe um membro com o mesmo CPF e RG. Cancele e use Atualizar este cadastro.\n\n" : "") +
        "A pessoa vira membro oficial do SIGM e o pré-cadastro fica no histórico como aprovado.",
      botao: "Aprovar e cadastrar",
    });
    if (!confirmado) return;
    await executar(null, async () => {
      let r = await api(`/api/pre-cadastros/${d.id}/aprovar`, { method: "POST", json: {} });
      if (!r.ok && r.dados.nivel === "medio") {
        const seguir = await perguntar({
          titulo: "Possível duplicidade",
          texto: `${r.dados.duplicidades} cadastro(s) parecido(s) foram encontrados. Pode ser coincidência de família ou de contato.\n\nSe for a mesma pessoa, use Atualizar este cadastro. Cadastrar como nova pessoa mesmo assim?`,
          botao: "Cadastrar como nova pessoa",
        });
        if (!seguir) return;
        r = await api(`/api/pre-cadastros/${d.id}/aprovar`, { method: "POST", json: { permitir_duplicidade: true } });
      }
      if (!r.ok) {
        avisar(r.dados.nivel === "alto"
          ? "Já existe um membro com o mesmo CPF ou RG. Se for a mesma pessoa, use Atualizar cadastro existente; se for cadastro enviado duas vezes, exclua este."
          : (r.dados.mensagem || "Não foi possível aprovar."), true);
        const alvo = document.getElementById("comparar");
        if (alvo) alvo.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      await depoisDeAcao(r.dados.mensagem || "Pré-cadastro aprovado.");
    });
  }

  async function atualizarExistente(candidato) {
    const d = estado.detalhe;
    const confirmado = await perguntar({
      titulo: "Atualizar cadastro existente",
      texto: `Atualizar o cadastro de ${candidato.nome || "membro"} (nº ${candidato.membro_id}) com os dados deste pré-cadastro?\n\nCampos preenchidos aqui substituem os atuais. Campos vazios mantêm o que já está no SIGM. Nenhum membro novo é criado.`,
      botao: "Atualizar cadastro",
    });
    if (!confirmado) return;
    await executar(null, async () => {
      const r = await api(`/api/pre-cadastros/${d.id}/atualizar-existente`, { method: "POST", json: { membro_id: candidato.membro_id } });
      if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível atualizar.", true); return; }
      await depoisDeAcao(`Cadastro de ${candidato.nome || "membro"} atualizado.`);
    });
  }

  async function excluir() {
    const d = estado.detalhe;
    const nome = d.campos.nome || "este pré-cadastro";
    const confirmado = await perguntar({
      titulo: "Excluir pré-cadastro",
      texto: `Excluir definitivamente o pré-cadastro de ${nome}?\n\nEsta ação não pode ser desfeita.` +
        (d.status === "aprovado" ? "\nO membro já cadastrado a partir dele NÃO será apagado." : ""),
      botao: "Excluir",
      perigo: true,
    });
    if (!confirmado) return;
    await executar(null, async () => {
      const r = await api(`/api/pre-cadastros/${d.id}/excluir`, { method: "POST", json: {} });
      if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível excluir.", true); return; }
      estado.detalhe = null;
      estado.selecionado = null;
      el.conteudo.hidden = true;
      el.vazio.hidden = false;
      fecharDetalheMobile();
      avisar("Pré-cadastro excluído.");
      await carregarLista();
    });
  }

  async function rejeitar() {
    const d = estado.detalhe;
    const motivo = await perguntar({
      titulo: "Rejeitar pré-cadastro",
      texto: "O registro continua no histórico. Escreva um motivo curto.",
      rotulo: "Motivo da rejeição",
      botao: "Rejeitar",
      perigo: true,
    });
    if (motivo === null) return;
    await executar(null, async () => {
      const r = await api(`/api/pre-cadastros/${d.id}/rejeitar`, { method: "POST", json: { motivo } });
      if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível rejeitar.", true); return; }
      await depoisDeAcao("Pré-cadastro rejeitado.");
    });
  }

  /* ---------- edição ---------- */
  function mascaraCpf(v) {
    const d = String(v || "").replace(/\D/g, "").slice(0, 11);
    if (d.length <= 3) return d;
    if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`;
    if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`;
    return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`;
  }

  function mascaraRg(v) {
    const t = String(v || "").trim();
    const l = t.replace(/[.\-\s]/g, "").toUpperCase();
    return /^\d{8}[0-9X]$/.test(l) ? `${l.slice(0, 2)}.${l.slice(2, 5)}.${l.slice(5, 8)}-${l[8]}` : t;
  }

  function desenharEdicao(d) {
    const form = h("form", { class: "form-edicao" });
    for (const [titulo, campos] of SECOES) {
      const grade = h("div", { class: "campos-edicao" });
      for (const campo of campos) {
        const longo = campo === "observacoes";
        const entrada = longo
          ? h("textarea", { name: campo }) : h("input", { type: "text", name: campo });
        entrada.value = d.campos[campo] || "";
        if (campo === "cpf") entrada.addEventListener("input", () => { entrada.value = mascaraCpf(entrada.value); });
        if (campo === "rg") entrada.addEventListener("blur", () => { entrada.value = mascaraRg(entrada.value); });
        grade.append(h("label", { class: longo ? "largo" : "" }, ROTULOS[campo] || campo, entrada));
      }
      form.append(h("section", { class: "secao" }, h("h3", null, titulo), grade));
    }
    form.append(h("div", { class: "barra-fixa" },
      h("button", { type: "submit", class: "btn btn-primario" }, "Salvar alterações"),
      h("button", { type: "button", class: "btn btn-secundario", onclick: () => { estado.editando = false; desenharDetalhe(); } }, "Cancelar")));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const dados = {};
      for (const campo of Object.keys(d.campos)) {
        if (form.elements[campo]) dados[campo] = form.elements[campo].value.trim();
      }
      const r = await api("/api/pre-cadastros/" + d.id, { method: "PUT", json: dados });
      if (!r.ok) { avisar(r.dados.erro || "Não foi possível salvar.", true); return; }
      estado.editando = false;
      avisar("Dados do pré-cadastro salvos.");
      await carregarLista();
      await abrirDetalhe(d.id);
    });
    el.conteudo.append(
      h("button", { type: "button", class: "btn btn-fantasma voltar", onclick: fecharDetalheMobile }, "Voltar para a lista"),
      h("h2", null, "Editar dados de " + (d.campos.nome || "pré-cadastro")), form);
  }

  /* ---------- eventos ---------- */
  el.abas.addEventListener("click", (e) => {
    const botao = e.target.closest("button[data-status]");
    if (!botao) return;
    estado.status = botao.dataset.status;
    for (const b of el.abas.querySelectorAll("button")) b.setAttribute("aria-selected", String(b === botao));
    carregarLista();
  });

  let temporizadorBusca;
  el.busca.addEventListener("input", () => {
    clearTimeout(temporizadorBusca);
    temporizadorBusca = setTimeout(() => { estado.busca = el.busca.value.trim(); carregarLista(); }, 250);
  });

  el.sincronizar.addEventListener("click", async () => {
    el.sincronizar.disabled = true;
    const texto = el.sincronizar.textContent;
    el.sincronizar.textContent = "Sincronizando...";
    try {
      const r = await api("/api/pre-cadastros/sincronizar", { method: "POST", json: {} });
      avisar(r.dados.mensagem || (r.ok ? "Sincronização concluída." : "Não foi possível sincronizar."), !r.ok);
      if (r.ok) await carregarLista();
    } catch (e) { avisar(e.message, true); }
    finally { el.sincronizar.disabled = false; el.sincronizar.textContent = texto; }
  });

  el.arquivo.addEventListener("change", async () => {
    const arquivo = el.arquivo.files[0];
    if (!arquivo) return;
    const form = new FormData();
    form.append("arquivo", arquivo);
    try {
      const r = await api("/api/pre-cadastros/importar", { method: "POST", form });
      avisar(r.dados.mensagem || "Importação concluída.", !r.ok);
      if (r.ok) await carregarLista();
    } catch (e) { avisar(e.message, true); }
    el.arquivo.value = "";
  });

  el.sair.addEventListener("click", async () => {
    const ok = await perguntar({ titulo: "Sair do SIGM", texto: "Deseja encerrar a sua sessão?", botao: "Sair" });
    if (!ok) return;
    await api("/api/logout", { method: "POST", json: {} });
    window.location.href = "/login";
  });

  carregarLista();
})();
