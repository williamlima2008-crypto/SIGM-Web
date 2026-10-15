(function () {
  "use strict";
  const { h, api, avisar, confirmar, formulario } = window.SIGMComum;
  const { perfis, senhaMinima } = window.SIGM_USUARIOS;
  const lista = document.getElementById("lista");
  const resumoChave = document.getElementById("resumo-chave");
  let eu = null;

  const rotuloPerfil = (p) => (perfis.find((x) => x[0] === p) || [p, p])[1];

  async function acao(promessa, padrao) {
    let r;
    try { r = await promessa; } catch (e) { avisar(e.message, true); return false; }
    avisar(r.dados.mensagem || (r.ok ? "Feito." : padrao), !r.ok);
    if (r.ok) carregar();
    return r.ok;
  }

  const validarSenha = (v) => {
    if ((v.senha || "").length < senhaMinima) return `A senha deve ter pelo menos ${senhaMinima} caracteres.`;
    if (v.senha !== v.confirmar) return "As senhas não conferem.";
    return null;
  };

  async function novo() {
    const v = await formulario({
      titulo: "Novo usuário", botao: "Cadastrar",
      campos: [
        { nome: "nome", rotulo: "Nome completo" },
        { nome: "usuario", rotulo: "Login", ajuda: "Sem espaços. É o que a pessoa digita para entrar." },
        { nome: "senha", rotulo: "Senha", tipo: "password" },
        { nome: "confirmar", rotulo: "Confirmar senha", tipo: "password" },
        { nome: "perfil", rotulo: "Perfil", opcoes: perfis, valor: "Usuario" },
      ],
      validar: (x) => (!x.nome.trim() || !x.usuario.trim()) ? "Informe nome e login." : validarSenha(x),
    });
    if (v) acao(api("/api/usuarios", { method: "POST", json: v }), "Não foi possível cadastrar.");
  }

  async function editar(u) {
    const v = await formulario({
      titulo: "Editar usuário",
      campos: [
        { nome: "nome", rotulo: "Nome completo", valor: u.nome },
        { nome: "usuario", rotulo: "Login", valor: u.usuario },
        { nome: "perfil", rotulo: "Perfil", opcoes: perfis, valor: u.perfil },
        { nome: "ativo", rotulo: "Usuário ativo", tipo: "checkbox", valor: u.ativo },
      ],
      validar: (x) => (!x.nome.trim() || !x.usuario.trim()) ? "Informe nome e login." : null,
    });
    if (v) acao(api(`/api/usuarios/${u.id}`, { method: "PUT", json: v }), "Não foi possível salvar.");
  }

  async function senha(u) {
    const v = await formulario({
      titulo: "Redefinir senha", texto: u.nome, botao: "Redefinir",
      campos: [
        { nome: "senha", rotulo: "Nova senha", tipo: "password" },
        { nome: "confirmar", rotulo: "Confirmar senha", tipo: "password" },
      ],
      validar: validarSenha,
    });
    if (v) acao(api(`/api/usuarios/${u.id}/senha`, { method: "POST", json: { senha: v.senha } }), "Não foi possível redefinir.");
  }

  async function alternar(u) {
    const bloquear = u.ativo;
    const ok = await confirmar({
      titulo: bloquear ? "Bloquear usuário?" : "Desbloquear usuário?",
      texto: bloquear ? `${u.nome} não conseguirá mais entrar.` : `${u.nome} poderá entrar novamente.`,
      botao: bloquear ? "Bloquear" : "Desbloquear", perigo: bloquear,
    });
    if (ok) acao(api(`/api/usuarios/${u.id}/status`, { method: "POST", json: { ativo: !u.ativo } }), "Não foi possível alterar.");
  }

  async function excluir(u) {
    const ok = await confirmar({ titulo: "Excluir usuário?", texto: `${u.nome} (${u.usuario}) será excluído. Isso não pode ser desfeito.`, botao: "Excluir", perigo: true });
    if (ok) acao(api(`/api/usuarios/${u.id}/excluir`, { method: "POST", json: {} }), "Não foi possível excluir.");
  }

  async function chave() {
    const ok = await confirmar({
      titulo: "Gerar chave de recuperação?",
      texto: "Com a chave, a senha pode ser redefinida na tela de login do desktop caso seja esquecida.\n\nSe já existir uma chave, gerar outra INVALIDA a anterior. A nova chave aparece uma única vez.",
      botao: "Gerar chave",
    });
    if (!ok) return;
    let r;
    try { r = await api("/api/usuarios/chave-recuperacao", { method: "POST", json: {} }); }
    catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(r.dados.mensagem || "Não foi possível gerar a chave.", true); return; }
    carregar();
    await formulario({
      titulo: "Sua chave de recuperação", botao: "Já guardei",
      texto: "Anote e guarde em local seguro. Ela não será mostrada de novo.",
      campos: [{ nome: "chave", rotulo: "Chave", valor: r.dados.chave }],
    });
  }

  async function carregar() {
    let r;
    try { r = await api("/api/usuarios"); } catch (e) { avisar(e.message, true); return; }
    if (!r.ok) { avisar(r.dados.erro || "Não foi possível carregar os usuários.", true); return; }
    eu = r.dados.eu;
    const c = r.dados.chave;
    resumoChave.textContent = c.existe ? `Chave de recuperação gerada${c.criada_em ? " em " + c.criada_em : ""}.` : "Ainda não há chave de recuperação de senha.";
    lista.replaceChildren();
    for (const u of r.dados.itens) {
      lista.append(h("li", { class: "cartao" },
        h("span", { class: "cartao-corpo" },
          h("strong", { class: "cartao-nome" }, u.nome + (u.id === eu ? " (você)" : "")),
          h("span", { class: "item-sub" }, `${u.usuario} · ${rotuloPerfil(u.perfil)}`)),
        h("span", { class: "selo " + (u.ativo ? "selo-aprovado" : "selo-rejeitado") }, u.ativo ? "Ativo" : "Bloqueado"),
        h("span", { class: "cartao-acoes" },
          h("button", { type: "button", class: "btn btn-secundario btn-pequeno", onclick: () => editar(u) }, "Editar"),
          h("button", { type: "button", class: "btn btn-secundario btn-pequeno", onclick: () => senha(u) }, "Senha"),
          u.id !== eu && h("button", { type: "button", class: "btn btn-secundario btn-pequeno", onclick: () => alternar(u) }, u.ativo ? "Bloquear" : "Desbloquear"),
          u.id !== eu && h("button", { type: "button", class: "btn btn-perigo btn-pequeno", onclick: () => excluir(u) }, "Excluir"))));
    }
  }

  document.getElementById("btn-novo-usuario").addEventListener("click", novo);
  document.getElementById("btn-chave").addEventListener("click", chave);
  carregar();
})();
