/*
    This file is executed as a pre-step script execution of the 'Run System Tests' step.
    In it, we generate a suites.json.
*/

// quickbuild vars
systemTestsSuitesPath = vars.get('system_tests_suites_path')

// parsed quickbuild vars

allSuitesPath = vars.getValue("cosmo_test_home_dir") + "-dan/cloudify-system-tests/vagrant/suites.json"
testsSuites = vars.get('system_tests_suites').asList()
isCustomSuite = vars.getValue('system_tests_custom_suite')
customSuiteName = vars.getValue('system_tests_custom_suite_name')
customTestsToRun = vars.getValue('system_tests_custom_tests_to_run')
customCloudifyConfig = vars.getValue('system_tests_custom_cloudify_config')
customHandlerModule = vars.getValue('system_tests_custom_handler_module')

// Create the temp file to be used as suites.json
suitesJsonFile = File.createTempFile("suites-",".json")

// Set the variable to be used when executing the system tests script
// will be translated to TEST_SUITES_PATH
systemTestsSuitesPath.setValue(suitesJsonFile.getAbsolutePath())

/*
if (isCustomSuite) {
    suites = [[
        'suite_name': customSuiteName,
        'tests_to_run': customTestsToRun,
        'cloudify_test_config': customCloudifyConfig,
        'cloudify_test_handler_module': customHandlerModule
    ]]
} else {
    jsonInput = new groovy.json.JsonSlurper()
    allSuites = jsonInput.parse(new File(allSuitesPath))
    suites = []
    for (suite in allSuites) {
        if (testsSuites.containes(suite.suite_name)) {
            suites.add(suite)
        }
    }
}

jsonOutput = new groovy.json.JsonBuilder()
suitesJsonFile.write(jsonOutput(suites).toPrettyString())
*/
import groovy.lang.GroovySystem
suitesJsonFile.write(GroovySystem.getVersion())
