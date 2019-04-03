function onReady() {
  var stacks = document.getElementsByClassName("selectStackOption");
  for (var i = 0; i < stacks.length; i++) {
    stacks[i].addEventListener(
      "click",
      function(data) {
        var stack_name = data.target.text;
        selectStack(stack_name);
        $("#takeThreadDumps").removeAttr("disabled");
        $("#takeHeapDumps").removeAttr("disabled");
      },
      false
    );
  }

  $("#action-button").on("click", performRestart);
}

function performRestart() {
  var stack_name = scrapePageForStackName();
  var url =
    baseUrl +
    "/do" +
    action +
    "/" +
    region +
    "/" +
    stack_name +
    "/" +
    document.getElementById("takeThreadDumps").checked +
    "/" +
    document.getElementById("takeHeapDumps").checked;

  send_http_get_request(url);
  redirectToLog(stack_name);
}
