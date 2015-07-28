// Sebastien Renard - 2015
// GPL v3
// Inspired by the work of https://github.com/dobarkod/django-casper

// Init
casper.test.comment('Casper test of js error and missing resources in console');

var errors = [];
var resourceErrors = [];

var urls = casper.cli.options['urls'].split(",");

casper.options.viewportSize = { width: 1024, height: 768 };
casper.options.timeout = 60000;
casper.options.onTimeout = function() {
    casper.die("Timed out", 1);
};

// Add cookie for authentication with django client session id
phantom.addCookie({
                    name: casper.cli.options["cookie-name"],
                    value: casper.cli.options["cookie-value"],
                    domain: "localhost",
                });


// Error listener
casper.on("page.error", function(msg, trace) {
    casper.echo("Error:    " + msg, "ERROR");
    casper.echo("file:     " + trace[0].file, "WARNING");
    casper.echo("line:     " + trace[0].line, "WARNING");
    casper.echo("function: " + trace[0]["function"], "WARNING");
    errors.push(msg);
});

// Missing resource listener
casper.on('resource.received', function(resource) {
    var status = resource.status;
    if(status >= 400) {
        casper.echo('Resource ' + resource.url + ' failed to load (' + status + ')', 'error');

        resourceErrors.push({
            url: resource.url,
            status: resource.status
        });
    }
});

casper.echo("Let's start");
// Let's run on all URLS
casper.start().eachThen(urls, function(response) {
  casper.thenOpen(response.data, function(response) {
    casper.echo('Opened ' + response.url);
    casper.test.assertEqual(response.status, 200, "Checking status 200 Ok");
  });
});

casper.run(function() {
    this.echo('End of JS tests');
    this.test.assert(resourceErrors.length == 0, "Test JS resource error.");
    this.test.assert(errors.length == 0, "Test JS console code error.");
    this.exit(); // <--- don't forget me!);
});

