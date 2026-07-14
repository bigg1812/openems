(function () {
  try {
    var stored = localStorage.getItem("miniEmsTheme");
    document.documentElement.setAttribute("data-theme", stored === "dark" ? "dark" : "light");
  } catch (error) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
