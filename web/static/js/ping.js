(function () {
  // Avisa o SIGM que a janela continua aberta (permite encerrar o servidor ao fechar).
  function ping() { fetch("/api/ping", { cache: "no-store" }).catch(function () {}); }
  ping();
  setInterval(ping, 5000);
})();
