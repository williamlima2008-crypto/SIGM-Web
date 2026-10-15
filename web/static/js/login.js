(function () {
  "use strict";
  const CABECALHOS = { "Content-Type": "application/json", "X-SIGM": "1" };

  async function enviar(caminho, corpo) {
    const resposta = await fetch(caminho, { method: "POST", headers: CABECALHOS, body: JSON.stringify(corpo) });
    const dados = await resposta.json().catch(() => ({}));
    return { ok: resposta.ok, dados };
  }
  const valores = (form) => Object.fromEntries(new FormData(form));
  const SEM_CONEXAO = "Não foi possível falar com o SIGM. Confira se ele está aberto.";

  function mostrar(no, texto, bom) {
    no.textContent = texto;
    no.classList.toggle("ok-texto", !!bom);
    no.hidden = false;
  }

  // ---------- login ----------
  const form = document.getElementById("form-login");
  if (form) {
    const erro = document.getElementById("login-erro");
    const botao = form.querySelector("button[type=submit]");
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      erro.hidden = true;
      botao.disabled = true;
      try {
        const r = await enviar("/api/login", { usuario: form.usuario.value, senha: form.senha.value });
        if (r.ok) { window.location.href = "/"; return; }
        mostrar(erro, r.dados.erro || "Não foi possível entrar.");
        form.senha.value = "";
        form.senha.focus();
      } catch (e) {
        mostrar(erro, SEM_CONEXAO);
      } finally {
        botao.disabled = false;
      }
    });

    // ---------- recuperar senha ----------
    const rec = document.getElementById("form-recuperar");
    const msg = document.getElementById("recuperar-msg");
    document.getElementById("btn-esqueci").addEventListener("click", () => {
      rec.usuario.value = form.usuario.value;
      form.hidden = true; rec.hidden = false; msg.hidden = true;
      (rec.usuario.value ? rec.chave : rec.usuario).focus();
    });
    document.getElementById("btn-voltar-login").addEventListener("click", () => {
      rec.hidden = true; form.hidden = false; form.usuario.focus();
    });
    rec.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      msg.hidden = true;
      const botaoRec = rec.querySelector("button[type=submit]");
      botaoRec.disabled = true;
      try {
        const r = await enviar("/api/recuperar-senha", valores(rec));
        if (r.ok) {
          const usuario = rec.usuario.value;
          rec.reset(); rec.hidden = true; form.hidden = false;
          form.usuario.value = usuario; form.senha.value = ""; form.senha.focus();
          mostrar(erro, r.dados.mensagem, true);
        } else {
          mostrar(msg, r.dados.mensagem || "Não foi possível redefinir a senha.");
        }
      } catch (e) {
        mostrar(msg, SEM_CONEXAO);
      } finally {
        botaoRec.disabled = false;
      }
    });
  }

  // ---------- primeiro acesso ----------
  const primeiro = document.getElementById("form-primeiro");
  if (primeiro) {
    const erro = document.getElementById("primeiro-erro");
    const bloco = document.getElementById("chave-bloco");
    primeiro.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      erro.hidden = true;
      const botao = primeiro.querySelector("button[type=submit]");
      botao.disabled = true;
      try {
        const r = await enviar("/api/primeiro-acesso", valores(primeiro));
        if (!r.ok) { mostrar(erro, r.dados.mensagem || "Não foi possível concluir."); return; }
        primeiro.hidden = true;
        document.querySelector(".aviso-leve").hidden = true;
        document.getElementById("chave-texto").textContent = r.dados.chave || "(gere a chave depois, em Usuários)";
        bloco.hidden = false;
      } catch (e) {
        mostrar(erro, SEM_CONEXAO);
      } finally {
        botao.disabled = false;
      }
    });
    document.getElementById("btn-chave-ok").addEventListener("click", () => { window.location.href = "/login"; });
  }
})();
