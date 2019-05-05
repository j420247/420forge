function onReady() {
  addStackDropdown();
  addDefaultActionButtonListener();

  $("#nodesCount").bind('nodeCountChanged', function(e) {
    var number = parseInt($("#nodesCount").text());
    if (number > 1) {
      $("#rebuildSingleNodeWarning").hide();
    } else {
      $("#rebuildSingleNodeWarning").show();
    }
  })
}
