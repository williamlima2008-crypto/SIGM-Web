(function () {
  "use strict";

  const ROTULOS = window.SIGM.rotulos;
  const SECOES = window.SIGM.secoes;
  const CAMPOS_DATA = new Set(window.SIGM.camposData);
  const FUNCOES = window.SIGM.funcoes;
  const STATUS_PADRAO = window.SIGM.statusPadrao;

  const estado = {
    status: "", busca: "", itens: [], contagem: {},
    selecionado: null, detalhe: null, modo: "ver", doc: null, // ver | editar | novo | documento
  };
  const el = {
    lista: document.getElementById("lista"),
    busca: document.getElementById("busca"),
    abas: document.getElementById("abas"),
    contador: document.getElementById("contador"),
    vazio: document.getElementById("detalhe-vazio"),
    conteudo: document.getElementById("detalhe-conteudo"),
    painel: document.getElementById("detalhe"),
    novo: document.getElementById("btn-novo"),
    arquivoFoto: document.getElementById("arquivo-foto"),
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
    if (resposta.status === 401) { (window.sigmPermitirSaida && window.sigmPermitirSaida(), window.location.href = "/login"); throw new Error("Sessão expirada."); }
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

  function mensagemErro(r, padrao) {
    return (r.dados && (r.dados.mensagem || r.dados.erro)) || padrao;
  }

  function iniciais(nome) {
    const partes = String(nome || "").trim().split(/\s+/).filter(Boolean);
    if (!partes.length) return "?";
    const primeira = partes[0][0];
    const ultima = partes.length > 1 ? partes[partes.length - 1][0] : "";
    return (primeira + ultima).toUpperCase();
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

  function perguntar({ titulo, texto, botao = "Confirmar", perigo = false }) {
    return new Promise((resolver) => {
      dlg.titulo.textContent = titulo;
      dlg.texto.textContent = texto || "";
      dlg.texto.hidden = !texto;
      dlg.campo.hidden = true;
      dlg.ok.textContent = botao;
      dlg.ok.className = "btn " + (perigo ? "btn-perigo" : "btn-primario");
      let resultado = false;
      const fechar = () => {
        dlg.caixa.close();
        dlg.form.removeEventListener("submit", enviar);
        dlg.cancelar.removeEventListener("click", cancelar);
        dlg.caixa.removeEventListener("cancel", cancelar);
        resolver(resultado);
      };
      const enviar = (e) => { e.preventDefault(); resultado = true; fechar(); };
      const cancelar = (e) => { if (e) e.preventDefault(); resultado = false; fechar(); };
      dlg.form.addEventListener("submit", enviar);
      dlg.cancelar.addEventListener("click", cancelar);
      dlg.caixa.addEventListener("cancel", cancelar);
      dlg.caixa.showModal();
      dlg.ok.focus();
    });
  }

  /* ---------- máscaras (iguais às do desktop) ---------- */
  const soDigitos = (v) => String(v || "").replace(/\D/g, "");

  function mascaraCpf(v) {
    const d = soDigitos(v).slice(0, 11);
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
  function mascaraCep(v) {
    const d = soDigitos(v).slice(0, 8);
    return d.length <= 5 ? d : `${d.slice(0, 5)}-${d.slice(5)}`;
  }
  function mascaraData(v) {
    const d = soDigitos(v).slice(0, 8);
    if (d.length <= 2) return d;
    if (d.length <= 4) return `${d.slice(0, 2)}/${d.slice(2)}`;
    return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
  }

  /* ---------- lista ---------- */
  function desenharAbas() {
    const ordem = [...STATUS_PADRAO];
    for (const chave of Object.keys(estado.contagem)) {
      if (chave !== "todos" && !ordem.includes(chave)) ordem.push(chave);
    }
    const abas = [["", "Todos", estado.contagem.todos || 0]];
    for (const nome of ordem) {
      const n = estado.contagem[nome] || 0;
      if (n || nome === estado.status) abas.push([nome, nome, n]);
    }
    el.abas.replaceChildren(...abas.map(([valor, rotulo, n]) =>
      h("button", {
        type: "button", role: "tab", "data-status": valor,
        "aria-selected": String(valor === estado.status),
      }, rotulo + " ", h("span", { class: "n" }, `(${n})`))));
  }

  async function carregarLista() {
    const params = new URLSearchParams();
    if (estado.status) params.set("status", estado.status);
    if (estado.busca) params.set("q", estado.busca);
    let r;
    try { r = await api("/api/membros?" + params); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(mensagemErro(r, "Não foi possível carregar a lista."), true); return; }
    estado.itens = r.dados.itens;
    estado.contagem = r.dados.contagem;
    desenharAbas();
    desenharLista();
  }

  function desenharLista() {
    el.lista.replaceChildren();
    const total = estado.contagem.todos || 0;
    el.contador.textContent = estado.itens.length === total
      ? `${total} ${total === 1 ? "membro" : "membros"}`
      : `${estado.itens.length} de ${total} membros`;
    if (!estado.itens.length) {
      el.lista.append(h("li", { class: "lista-vazia" },
        estado.busca || estado.status
          ? "Nenhum membro encontrado com esse filtro."
          : "Nenhum membro cadastrado ainda. Use Novo membro para começar."));
      return;
    }
    for (const item of estado.itens) {
      const botao = h("button", {
        type: "button", class: "item item-membro",
        "aria-current": item.id === estado.selecionado ? "true" : "false",
        onclick: () => abrirFicha(item.id),
      },
        h("span", { class: "avatar", "aria-hidden": "true" }, iniciais(item.nome)),
        h("span", { class: "item-corpo" },
          h("span", { class: "item-nome", style: "display:block" }, item.nome || "(sem nome)"),
          h("span", { class: "item-sub" },
            [item.celular, item.cidade].filter(Boolean).join(" · ") || "Sem celular ou cidade")),
        h("span", { class: "item-lado" },
          item.status && h("span", { class: "selo selo-status selo-" + item.status }, item.status),
          item.cargo && h("span", { style: "display:block;margin-top:2px" }, item.cargo)),
      );
      el.lista.append(h("li", null, botao));
    }
  }

  /* ---------- ficha ---------- */
  function abrirMobile() { document.body.classList.add("detalhe-aberto"); }
  function fecharMobile() { document.body.classList.remove("detalhe-aberto"); }

  async function abrirFicha(id, modo = "ver") {
    estado.selecionado = id;
    desenharLista();
    let r;
    try { r = await api("/api/membros/" + id); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(mensagemErro(r, "Não foi possível abrir o membro."), true); return; }
    estado.detalhe = r.dados;
    estado.modo = modo;
    desenharDetalhe();
    abrirMobile();
    el.painel.scrollTop = 0;
  }

  function fecharFicha() {
    estado.selecionado = null;
    estado.detalhe = null;
    estado.modo = "ver";
    el.conteudo.hidden = true;
    el.vazio.hidden = false;
    fecharMobile();
    desenharLista();
  }

  function botaoVoltar() {
    return h("button", { type: "button", class: "btn btn-fantasma voltar", onclick: fecharMobile }, "Voltar para a lista");
  }

  function urlFoto(d) {
    return `/api/membros/${d.id}/foto?v=${d.versao_foto || 0}`;
  }

  function desenharDetalhe() {
    const d = estado.detalhe;
    el.vazio.hidden = true;
    el.conteudo.hidden = false;
    el.conteudo.replaceChildren();
    if (estado.modo === "editar" || estado.modo === "novo") { desenharFormulario(); return; }
    if (estado.modo === "documento") { desenharFormularioDocumento(); return; }

    const c = d.campos;
    const nome = c.nome || "(sem nome)";
    const foto = d.tem_foto
      ? h("img", { class: "foto", src: urlFoto(d), alt: "Foto de " + nome })
      : h("div", { class: "foto foto-vazia" }, "Sem foto");

    const bloco = h("div", { class: "foto-bloco" }, foto,
      h("div", { class: "foto-botoes" },
        h("button", { type: "button", class: "btn btn-secundario btn-pequeno", onclick: escolherFoto },
          d.tem_foto ? "Trocar foto" : "Adicionar foto"),
        d.tem_foto && h("button", { type: "button", class: "btn-texto", onclick: removerFoto }, "Remover foto")));

    const topo = h("div", { class: "det-topo" }, bloco,
      h("div", { class: "det-id" },
        h("h2", null, nome),
        h("div", { class: "det-meta" },
          c.status && h("span", { class: "selo selo-status selo-" + c.status }, c.status),
          c.cargo && c.cargo !== "Nenhuma" && h("span", { class: "selo selo-cargo" }, c.cargo),
          h("span", null, "Código " + d.id))));

    const acoes = h("div", { class: "acoes" },
      h("button", { type: "button", class: "btn btn-primario", onclick: () => { estado.modo = "editar"; desenharDetalhe(); el.painel.scrollTop = 0; } }, "Editar dados"));

    el.conteudo.append(botaoVoltar(), topo, acoes, blocoDocumentos(), blocoArquivos());

    for (const [titulo, campos] of SECOES) {
      const lista = h("dl", { class: "dados" });
      for (const campo of campos) {
        const valor = c[campo];
        let conteudo = valor || "—";
        if (valor && (campo === "celular" || campo === "telefone")) {
          conteudo = h("a", { href: "tel:" + soDigitos(valor) }, valor);
        } else if (valor && campo === "email") {
          conteudo = h("a", { href: "mailto:" + valor }, valor);
        }
        lista.append(h("div", { class: "dado" + (campo === "observacoes" ? " largo" : "") },
          h("dt", null, ROTULOS[campo] || campo),
          h("dd", null, conteudo)));
      }
      el.conteudo.append(h("section", { class: "secao" }, h("h3", null, titulo), lista));
    }

    el.conteudo.append(h("div", { class: "zona-perigo" },
      h("button", { type: "button", class: "btn btn-perigo", onclick: excluir }, "Excluir membro")));
  }

  /* ---------- foto ---------- */
  function escolherFoto() {
    el.arquivoFoto.value = "";
    el.arquivoFoto.onchange = async () => {
      const arquivo = el.arquivoFoto.files[0];
      if (!arquivo || !estado.detalhe) return;
      const form = new FormData();
      form.append("foto", arquivo);
      avisar("Enviando a foto...");
      try {
        const r = await api(`/api/membros/${estado.detalhe.id}/foto`, { method: "POST", form });
        if (!r.ok) { avisar(mensagemErro(r, "Não foi possível salvar a foto."), true); return; }
        avisar("Foto salva.");
        await abrirFicha(estado.detalhe.id);
      } catch (e) { avisar(e.message, true); }
    };
    el.arquivoFoto.click();
  }

  async function removerFoto() {
    const ok = await perguntar({
      titulo: "Remover a foto?",
      texto: "O membro fica sem foto. Os documentos novos sairão sem ela.",
      botao: "Remover foto", perigo: true,
    });
    if (!ok) return;
    try {
      const r = await api(`/api/membros/${estado.detalhe.id}/foto`, { method: "DELETE" });
      if (!r.ok) { avisar(mensagemErro(r, "Não foi possível remover a foto."), true); return; }
      avisar("Foto removida.");
      await abrirFicha(estado.detalhe.id);
    } catch (e) { avisar(e.message, true); }
  }

  /* ---------- excluir ---------- */
  async function excluir() {
    const d = estado.detalhe;
    const ok = await perguntar({
      titulo: "Excluir este membro?",
      texto: `${d.campos.nome || "O membro"} será excluído.\n\nEssa ação não poderá ser desfeita.`,
      botao: "Excluir", perigo: true,
    });
    if (!ok) return;
    try {
      const r = await api(`/api/membros/${d.id}/excluir`, { method: "POST", json: {} });
      if (!r.ok) { avisar(mensagemErro(r, "Não foi possível excluir."), true); return; }
      avisar("Membro excluído.");
      fecharFicha();
      await carregarLista();
    } catch (e) { avisar(e.message, true); }
  }

  /* ---------- formulário (editar / novo) ---------- */
  function criarCampo(campo, valor) {
    if (campo === "observacoes") {
      const area = h("textarea", { name: campo });
      area.value = valor || "";
      return area;
    }
    if (campo === "cargo" || campo === "status") {
      const opcoes = campo === "cargo" ? [...FUNCOES] : [...STATUS_PADRAO];
      const atual = valor || (campo === "cargo" ? "Nenhuma" : "Membro");
      if (!opcoes.includes(atual)) opcoes.push(atual);
      const select = h("select", { name: campo }, opcoes.map((o) => h("option", { value: o }, o)));
      select.value = atual;
      return select;
    }
    const entrada = h("input", { type: "text", name: campo });
    entrada.value = valor || "";
    if (campo === "cpf") entrada.addEventListener("input", () => { entrada.value = mascaraCpf(entrada.value); });
    else if (campo === "rg") entrada.addEventListener("blur", () => { entrada.value = mascaraRg(entrada.value); });
    else if (campo === "cep") entrada.addEventListener("input", () => { entrada.value = mascaraCep(entrada.value); });
    else if (CAMPOS_DATA.has(campo)) {
      entrada.setAttribute("inputmode", "numeric");
      entrada.setAttribute("placeholder", "DD/MM/AAAA");
      entrada.addEventListener("input", () => { entrada.value = mascaraData(entrada.value); });
    } else if (campo === "celular" || campo === "telefone") {
      entrada.setAttribute("inputmode", "tel");
    } else if (campo === "email") {
      entrada.setAttribute("inputmode", "email");
      entrada.setAttribute("autocapitalize", "none");
    }
    return entrada;
  }

  function desenharFormulario() {
    const novo = estado.modo === "novo";
    const d = estado.detalhe;
    const valores = novo ? { status: "Membro", cargo: "Nenhuma" } : d.campos;
    const form = h("form", { class: "form-edicao", novalidate: true });
    let fotoNova = null;

    if (novo) {
      const previa = h("div", { class: "foto foto-vazia" }, "Sem foto");
      const entradaFoto = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp,image/bmp", hidden: true });
      entradaFoto.addEventListener("change", () => {
        fotoNova = entradaFoto.files[0] || null;
        previa.replaceChildren();
        if (fotoNova) {
          previa.className = "foto";
          previa.style.cssText = `background:center/cover url(${URL.createObjectURL(fotoNova)})`;
        } else {
          previa.className = "foto foto-vazia";
          previa.style.cssText = "";
          previa.textContent = "Sem foto";
        }
      });
      form.append(h("div", { class: "det-topo" },
        h("div", { class: "foto-bloco" }, previa, entradaFoto,
          h("button", { type: "button", class: "btn btn-secundario btn-pequeno", onclick: () => entradaFoto.click() }, "Escolher foto")),
        h("div", { class: "det-id" }, h("p", { class: "det-meta" }, "A foto é opcional. Você pode adicioná-la depois na ficha."))));
    }

    for (const [titulo, campos] of SECOES) {
      const grade = h("div", { class: "campos-edicao" });
      for (const campo of campos) {
        const longo = campo === "observacoes";
        const obrigatorio = campo === "nome";
        grade.append(h("label", { class: longo || campo === "nome" ? "largo" : "" },
          (ROTULOS[campo] || campo) + (obrigatorio ? " *" : ""),
          criarCampo(campo, valores[campo])));
      }
      form.append(h("section", { class: "secao" }, h("h3", null, titulo), grade));
    }

    const salvar = h("button", { type: "submit", class: "btn btn-primario" }, novo ? "Cadastrar membro" : "Salvar alterações");
    form.append(h("div", { class: "barra-fixa" }, salvar,
      h("button", {
        type: "button", class: "btn btn-secundario",
        onclick: () => {
          if (novo) fecharFicha();
          else { estado.modo = "ver"; desenharDetalhe(); }
        },
      }, "Cancelar")));

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const dados = {};
      for (const campos of SECOES.map((s) => s[1])) {
        for (const campo of campos) if (form.elements[campo]) dados[campo] = form.elements[campo].value.trim();
      }
      if (!dados.nome) { avisar("O campo Nome completo é obrigatório.", true); form.elements.nome.focus(); return; }
      salvar.disabled = true;
      try {
        const r = novo
          ? await api("/api/membros", { method: "POST", json: dados })
          : await api("/api/membros/" + d.id, { method: "PUT", json: dados });
        if (!r.ok) { avisar(mensagemErro(r, "Não foi possível salvar."), true); return; }
        const id = novo ? r.dados.id : d.id;
        if (novo && fotoNova) {
          const f = new FormData();
          f.append("foto", fotoNova);
          const rf = await api(`/api/membros/${id}/foto`, { method: "POST", form: f });
          if (!rf.ok) avisar("Membro cadastrado, mas a foto não foi salva: " + mensagemErro(rf, ""), true);
          else avisar("Membro cadastrado.");
        } else {
          avisar(novo ? "Membro cadastrado." : "Dados salvos.");
        }
        await carregarLista();
        await abrirFicha(id);
      } catch (erro) { avisar(erro.message, true); }
      finally { salvar.disabled = false; }
    });

    el.conteudo.append(
      botaoVoltar(),
      h("h2", null, novo ? "Novo membro" : "Editar dados de " + (valores.nome || "membro")),
      form);
    const primeiro = form.elements.nome;
    if (primeiro && novo) primeiro.focus();
  }


  /* ---------- arquivos anexados ---------- */
  function pedirTexto({ titulo, rotulo, valor }) {
    return new Promise((resolver) => {
      dlg.titulo.textContent = titulo;
      dlg.texto.hidden = true;
      dlg.campo.hidden = false;
      dlg.rotulo.textContent = rotulo;
      dlg.entrada.value = valor || "";
      dlg.ok.textContent = "Salvar";
      dlg.ok.className = "btn btn-primario";
      let resultado = null;
      const fechar = () => {
        dlg.caixa.close();
        dlg.campo.hidden = true;
        dlg.form.removeEventListener("submit", enviar);
        dlg.cancelar.removeEventListener("click", cancelar);
        dlg.caixa.removeEventListener("cancel", cancelar);
        resolver(resultado);
      };
      const enviar = (e) => { e.preventDefault(); resultado = dlg.entrada.value.trim() || null; fechar(); };
      const cancelar = (e) => { if (e) e.preventDefault(); resultado = null; fechar(); };
      dlg.form.addEventListener("submit", enviar);
      dlg.cancelar.addEventListener("click", cancelar);
      dlg.caixa.addEventListener("cancel", cancelar);
      dlg.caixa.showModal();
      dlg.entrada.focus();
    });
  }

  function blocoArquivos() {
    const corpo = h("div", { class: "arquivos" }, h("p", { class: "item-sub" }, "Carregando..."));
    atualizarArquivos(corpo);
    return h("section", { class: "secao", id: "secao-arquivos" }, h("h3", null, "Arquivos anexados"), corpo);
  }

  async function atualizarArquivos(corpo) {
    const id = estado.detalhe.id;
    let r;
    try { r = await api(`/api/membros/${id}/arquivos`); }
    catch (e) { corpo.replaceChildren(h("p", { class: "item-sub" }, e.message)); return; }
    if (!r.ok) { corpo.replaceChildren(h("p", { class: "item-sub" }, "Não foi possível carregar os arquivos.")); return; }

    const tipo = h("select", { "aria-label": "Tipo do arquivo" }, r.dados.tipos.map((t) => h("option", { value: t.valor }, t.rotulo)));
    const titulo = h("input", { type: "text", placeholder: "Título (ex.: RG frente e verso)", maxlength: "120", "aria-label": "Título" });
    const observacao = h("input", { type: "text", placeholder: "Observação (opcional)", maxlength: "200", "aria-label": "Observação" });
    const arquivo = h("input", { type: "file", accept: ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg", "aria-label": "Arquivo" });
    const enviar = h("button", { type: "button", class: "btn btn-primario btn-pequeno" }, "Anexar arquivo");
    enviar.addEventListener("click", async () => {
      if (!arquivo.files[0]) { avisar("Escolha um arquivo (PDF, PNG ou JPG).", true); return; }
      if (!titulo.value.trim()) { avisar("Informe o título do arquivo.", true); titulo.focus(); return; }
      const dados = new FormData();
      dados.append("arquivo", arquivo.files[0]);
      dados.append("tipo", tipo.value);
      dados.append("titulo", titulo.value.trim());
      dados.append("observacao", observacao.value.trim());
      enviar.disabled = true;
      try {
        const resposta = await fetch(`/api/membros/${id}/arquivos`, { method: "POST", headers: { "X-SIGM": "1" }, body: dados });
        const corpoResposta = await resposta.json().catch(() => ({}));
        avisar(corpoResposta.mensagem || (resposta.ok ? "Arquivo anexado." : "Não foi possível anexar."), !resposta.ok);
        if (resposta.ok) atualizarArquivos(corpo);
      } catch (e) { avisar("Não foi possível enviar o arquivo.", true); }
      finally { enviar.disabled = false; }
    });
    const formulario = h("div", { class: "arquivo-form" }, tipo, titulo, observacao, arquivo, enviar);

    const itens = r.dados.itens;
    const lista = itens.length
      ? h("ul", { class: "doc-historico" }, itens.map((a) => {
          const url = `/api/arquivos-membro/${a.id}/arquivo`;
          return h("li", null,
            h("span", null, h("strong", null, a.titulo), h("span", { class: "item-sub" },
              ` · ${a.tipo_rotulo} · ${a.data}` + (a.usuario ? ` · ${a.usuario}` : "") + (a.observacao ? ` · ${a.observacao}` : ""))),
            h("span", { class: "arquivo-acoes" },
              a.disponivel
                ? h("a", { href: url, target: "_blank", rel: "noopener" }, "Abrir")
                : h("span", { class: "item-sub" }, "Arquivo não encontrado"),
              h("button", { type: "button", class: "btn-texto", onclick: async () => {
                const novo = await pedirTexto({ titulo: "Renomear título", rotulo: "Novo título", valor: a.titulo });
                if (!novo) return;
                const x = await api(`/api/arquivos-membro/${a.id}`, { method: "PUT", json: { titulo: novo } });
                avisar(x.dados.mensagem || "Não foi possível renomear.", !x.ok);
                if (x.ok) atualizarArquivos(corpo);
              } }, "Renomear"),
              h("button", { type: "button", class: "btn-texto", onclick: async () => {
                const ok = await perguntar({ titulo: "Excluir arquivo?", texto: `“${a.titulo}” será excluído do disco e da ficha do membro.`, botao: "Excluir", perigo: true });
                if (!ok) return;
                const x = await api(`/api/arquivos-membro/${a.id}/excluir`, { method: "POST", json: { fisico: true } });
                avisar(x.dados.mensagem || "Não foi possível excluir.", !x.ok);
                if (x.ok) atualizarArquivos(corpo);
              } }, "Excluir")));
        }))
      : h("p", { class: "item-sub" }, "Nenhum arquivo anexado para este membro.");
    corpo.replaceChildren(formulario, lista);
  }

  /* ---------- documentos oficiais ---------- */
  function blocoDocumentos() {
    const corpo = h("div", { class: "docs" }, h("p", { class: "item-sub" }, "Carregando..."));
    atualizarDocumentos(corpo);
    return h("section", { class: "secao", id: "secao-documentos" }, h("h3", null, "Documentos oficiais"), corpo);
  }

  function abrirPdf(url) {
    const janela = window.open(url, "_blank");
    return !!janela;
  }

  async function atualizarDocumentos(corpo) {
    const id = estado.detalhe.id;
    let r;
    try { r = await api(`/api/membros/${id}/documentos`); }
    catch (e) { corpo.replaceChildren(h("p", { class: "item-sub" }, e.message)); return; }
    if (!r.ok) { corpo.replaceChildren(h("p", { class: "item-sub" }, "Não foi possível carregar os documentos.")); return; }
    const linhas = r.dados.catalogo.map((doc) => {
      const botao = h("button", { type: "button", class: "btn btn-primario btn-pequeno" },
        doc.formulario ? "Preencher e gerar" : "Gerar PDF");
      botao.addEventListener("click", async () => {
        if (doc.formulario) { estado.modo = "documento"; estado.doc = doc; desenharDetalhe(); el.painel.scrollTop = 0; return; }
        botao.disabled = true; botao.textContent = "Gerando...";
        try { await gerarDocumento(doc.slug, {}); }
        finally { botao.disabled = false; botao.textContent = "Gerar PDF"; }
      });
      return h("div", { class: "doc-linha" },
        h("div", { class: "doc-texto" }, h("strong", null, doc.titulo), h("span", { class: "item-sub" }, doc.descricao)),
        botao);
    });
    const historico = r.dados.historico;
    const lista = historico.length
      ? h("ul", { class: "doc-historico" }, historico.map((d) => h("li", null,
          h("span", null, h("strong", null, d.titulo), h("span", { class: "item-sub" },
            ` · ${d.data}` + (d.usuario ? ` · ${d.usuario}` : ""))),
          d.disponivel
            ? h("a", { href: `/api/documentos-emitidos/${d.id}/arquivo`, target: "_blank", rel: "noopener" }, "Abrir")
            : h("span", { class: "item-sub" }, "Arquivo não encontrado"))))
      : h("p", { class: "item-sub" }, "Nenhum documento emitido ainda.");
    corpo.replaceChildren(...linhas, h("h4", { class: "doc-sub" }, "Documentos emitidos"), lista);
  }

  async function gerarDocumento(slug, valores) {
    const id = estado.detalhe.id;
    let r;
    try { r = await api(`/api/membros/${id}/documentos/${slug}`, { method: "POST", json: valores }); }
    catch (e) { avisar(e.message, true); return false; }
    if (!r.ok) { avisar(mensagemErro(r, "Não foi possível gerar o documento."), true); return false; }
    const aberto = abrirPdf(r.dados.url);
    avisar(aberto ? r.dados.mensagem : r.dados.mensagem + " Use Abrir em Documentos emitidos.");
    return true;
  }

  function desenharFormularioDocumento() {
    const d = estado.detalhe;
    const doc = estado.doc;
    el.conteudo.replaceChildren(botaoVoltar(), h("p", { class: "item-sub" }, "Preparando o formulário..."));
    api(`/api/membros/${d.id}/documentos/${doc.slug}/formulario`).then((r) => {
      if (estado.modo !== "documento") return;
      if (!r.ok) {
        avisar(mensagemErro(r, "Não foi possível preparar o documento."), true);
        estado.modo = "ver"; desenharDetalhe(); return;
      }
      montarFormularioDocumento(r.dados);
    }).catch((e) => { avisar(e.message, true); estado.modo = "ver"; desenharDetalhe(); });
  }

  function montarFormularioDocumento(f) {
    const d = estado.detalhe;
    const doc = estado.doc;
    const form = h("form", { class: "form-edicao", novalidate: true });
    const entradas = {};

    if (f.automaticos.length) {
      const lista = h("dl", { class: "dados" });
      for (const a of f.automaticos) {
        lista.append(h("div", { class: "dado" }, h("dt", null, a.rotulo), h("dd", null, a.valor || "—")));
      }
      form.append(h("section", { class: "secao" }, h("h3", null, "Dados automáticos"), lista));
    }

    let usarAtual = null, dataEntrada = null;
    if (f.data) {
      usarAtual = h("input", { type: "checkbox", id: "usar-data-atual" });
      usarAtual.checked = true;
      dataEntrada = h("input", { type: "text", inputmode: "numeric", placeholder: "DD/MM/AAAA" });
      dataEntrada.value = f.data.valor;
      dataEntrada.disabled = true;
      usarAtual.addEventListener("change", () => {
        dataEntrada.disabled = usarAtual.checked;
        if (usarAtual.checked) dataEntrada.value = f.data.valor;
      });
      dataEntrada.addEventListener("input", () => { dataEntrada.value = mascaraData(dataEntrada.value); });
      form.append(h("section", { class: "secao" }, h("h3", null, "Data do documento"),
        h("div", { class: "campos-edicao" },
          h("label", { class: "marcar" }, usarAtual, "Usar data atual"),
          h("label", null, "Data", dataEntrada))));
    }

    const grade = h("div", { class: "campos-edicao" });
    for (const c of f.campos) {
      let entrada;
      if (c.tipo === "area") { entrada = h("textarea", { name: c.nome }); entrada.value = c.valor || ""; }
      else if (c.tipo === "simnao") {
        entrada = h("select", { name: c.nome },
          h("option", { value: "" }, "Não informado"), h("option", { value: "sim" }, "Sim"), h("option", { value: "nao" }, "Não"));
        entrada.value = c.valor || "";
      } else { entrada = h("input", { type: "text", name: c.nome }); entrada.value = c.valor || ""; }
      entradas[c.nome] = entrada;
      grade.append(h("label", { class: c.tipo === "area" ? "largo" : "" }, c.rotulo, entrada,
        c.ajuda && h("span", { class: "item-sub" }, c.ajuda)));
    }
    if (f.campos.length) form.append(h("section", { class: "secao" }, h("h3", null, "Campos editáveis"), grade));

    const gerar = h("button", { type: "submit", class: "btn btn-sucesso" }, "Gerar PDF");
    form.append(h("div", { class: "barra-fixa" }, gerar,
      h("button", { type: "button", class: "btn btn-secundario", onclick: () => { estado.modo = "ver"; desenharDetalhe(); } }, "Voltar à ficha")));

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const valores = {};
      for (const [nome, entrada] of Object.entries(entradas)) valores[nome] = entrada.value.trim();
      if (usarAtual) { valores.usar_data_atual = usarAtual.checked; valores.data_documento = dataEntrada.value.trim(); }
      gerar.disabled = true; gerar.textContent = "Gerando...";
      try {
        const ok = await gerarDocumento(doc.slug, valores);
        if (ok) { estado.modo = "ver"; desenharDetalhe(); }
      } finally { gerar.disabled = false; gerar.textContent = "Gerar PDF"; }
    });

    el.conteudo.replaceChildren(botaoVoltar(),
      h("h2", null, f.titulo), h("p", { class: "item-sub" }, d.campos.nome || ""), form);
  }

  /* ---------- eventos ---------- */
  el.abas.addEventListener("click", (e) => {
    const botao = e.target.closest("button[data-status]");
    if (!botao) return;
    estado.status = botao.dataset.status;
    carregarLista();
  });

  let temporizadorBusca;
  el.busca.addEventListener("input", () => {
    clearTimeout(temporizadorBusca);
    temporizadorBusca = setTimeout(() => { estado.busca = el.busca.value.trim(); carregarLista(); }, 250);
  });

  el.novo.addEventListener("click", () => {
    estado.selecionado = null;
    estado.detalhe = { id: null, campos: {} };
    estado.modo = "novo";
    desenharLista();
    desenharDetalhe();
    abrirMobile();
    el.painel.scrollTop = 0;
  });

  el.sair.addEventListener("click", async () => {
    const ok = await perguntar({ titulo: "Sair do SIGM", texto: "Deseja encerrar a sua sessão?", botao: "Sair" });
    if (!ok) return;
    await api("/api/logout", { method: "POST", json: {} });
    (window.sigmPermitirSaida && window.sigmPermitirSaida(), window.location.href = "/login");
  });

  carregarLista().then(() => {
    const id = Number(new URLSearchParams(window.location.search).get("abrir"));
    if (id) abrirFicha(id);
  });
})();
