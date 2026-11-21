<?php

use SebastianBergmann\CodeCoverage\CodeCoverage;

require __DIR__.'/../../vendor/autoload.php';

$report = require '/evidence/coverage.cov';
if (! $report instanceof CodeCoverage) {
    throw new RuntimeException('The PHPUnit coverage report is missing or invalid.');
}

$data = $report->getData();
$targets = [
    'app/Models/Asset.php' => ['availableForCheckout' => true, 'checkOut' => false],
    'app/Http/Requests/AssetCheckoutRequest.php' => ['rulesArray' => false],
    'app/Http/Controllers/Api/AssetsController.php' => ['checkout' => false, 'checkin' => false],
    'app/Policies/CheckoutablePermissionsPolicy.php' => ['checkout' => true, 'checkin' => true],
];
$results = [];
$passed = true;

foreach ($targets as $file => $methods) {
    $absolutePath = realpath(__DIR__.'/../../'.$file);
    $functions = $data->functionCoverage()[$absolutePath] ?? [];
    $fileLines = $data->lineCoverage()[$absolutePath] ?? [];
    foreach ($methods as $method => $enforced) {
        $matching = array_filter($functions, static fn ($name) => str_ends_with($name, '->'.$method)
            || str_ends_with($name, '::'.$method), ARRAY_FILTER_USE_KEY);
        $branches = reset($matching)['branches'] ?? [];
        if ($branches === []) {
            throw new RuntimeException("No Xdebug branch data for {$file}::{$method}.");
        }
        $start = min(array_column($branches, 'line_start'));
        $end = max(array_column($branches, 'line_end'));
        $statements = array_filter($fileLines, static fn ($hits, $line) => is_array($hits)
            && $line >= $start && $line <= $end, ARRAY_FILTER_USE_BOTH);
        $lineHits = count(array_filter($statements));
        $branchHits = count(array_filter(array_column($branches, 'hit')));
        $results[] = [
            'file' => $file, 'method' => $method,
            'lines_hit' => $lineHits, 'lines_total' => count($statements),
            'branches_hit' => $branchHits, 'branches_total' => count($branches),
            'required_complete' => $enforced,
        ];
        if ($enforced && ($lineHits !== count($statements) || $branchHits !== count($branches))) {
            $passed = false;
        }
    }
}

file_put_contents('/evidence/scoped-coverage.json', json_encode($results, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR).PHP_EOL);
foreach ($results as $method) {
    printf("%s::%s lines %d/%d branches %d/%d\n", $method['file'], $method['method'],
        $method['lines_hit'], $method['lines_total'], $method['branches_hit'], $method['branches_total']);
}
exit($passed ? 0 : 1);
