<?php

/**
 * ---------------------------------------------------------------------
 * THIS IS $allowed_origins code IS NOT PART OF THE ORIGINAL CORS PACKAGE.
 * IT IS A MODIFICATION BY SNIPE-IT TO ALLOW ADDING ALLOWED ORIGINS VIA THE ENV.
 * ---------------------------------------------------------------------
 *
 * Since we don't really want people editing config files (lest they get
 * overwritten later), this enables the person managing the Snipe-IT
 * installation to modify these values without modifying the code.
 *
 * Set CORS_ALLOWED_ORIGINS to the comma-delimited list of browser origins
 * that may call the API. Without a list, cross-origin access is disabled.
 */
$allowed_origins = array_values(array_filter(array_map('trim', explode(',', (string) env('CORS_ALLOWED_ORIGINS')))));

/**
 * Original Laravel CORS package config file modifications end here
 */

return [

    /*
    |--------------------------------------------------------------------------
    | Laravel CORS
    |--------------------------------------------------------------------------
    |
    | allowedOrigins, allowedHeaders and allowedMethods can be set to array('*')
    | to accept any value.
    |
    */

    'supports_credentials' => false,
    'allowed_origins' => $allowed_origins,
    'allowed_origins_patterns' => [],
    'allowed_headers' => ['*'],
    'allowed_methods' => ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    'exposed_headers' => [],
    'max_age' => 0,
    'paths' => ['api/*', 'sanctum/csrf-cookie', '.well-known/*', 'oauth/*', 'mcp/*'],

];
