$(document).ready(function() {
    var regions = document.getElementsByClassName("selectRegionOption");
    for (var i = 0; i < regions.length; i++) {
        regions[i].addEventListener("click", function (data) {
            var region = data.target.text;
            $("#regionSelector").text(region);
            $("#ebsSnapshotSelector").text("Select EBS snapshot");
            $("#rdsSnapshotSelector").text("Select RDS snapshot");
            getEbsSnapshots(region, document.getElementById("stackSelector").innerText);
            getRdsSnapshots(region, document.getElementById("stackSelector").innerText);
            getVPCs(region, document.getElementById("VPCDiv"));
        }, false);
    }
});