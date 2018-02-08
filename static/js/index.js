
$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            var stackName = data.target.text;
            $("#stackSelector").text(stackName);


        }, false);
    }
});