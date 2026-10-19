(function () {
  // Avisa o SIGM que a janela continua aberta (permite encerrar o servidor ao fechar).
  function ping() { fetch("/api/ping", { cache: "no-store" }).catch(function () {}); }
  ping();
  setInterval(ping, 5000);

  // Pede confirmacao ao fechar a janela (X) ou a aba. Navegacao interna
  // (links, formularios, F5/Ctrl+R, sair/login) nao pergunta nada.
  var saidaLivre = false;
  var soltar = function () { saidaLivre = true; setTimeout(function () { saidaLivre = false; }, 1500); };
  window.sigmPermitirSaida = soltar;
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest && e.target.closest("a[href]");
    if (a && !a.hasAttribute("download") && a.target !== "_blank") soltar();
  }, true);
  document.addEventListener("submit", soltar, true);
  document.addEventListener("keydown", function (e) {
    if (e.key === "F5" || ((e.ctrlKey || e.metaKey) && (e.key === "r" || e.key === "R"))) soltar();
  }, true);
  window.addEventListener("beforeunload", function (e) {
    if (saidaLivre) return;
    e.preventDefault();
    e.returnValue = "O SIGM está em uso. Deseja realmente fechar?";
    return e.returnValue;
  });
})();
