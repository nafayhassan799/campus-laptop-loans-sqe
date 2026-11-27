<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('assets', function (Blueprint $table) {
            $table->string('name', 255)->nullable()->change();
        });
    }

    public function down(): void
    {
        $length = DB::getDriverName() === 'sqlite' ? 'LENGTH' : 'CHAR_LENGTH';

        if (DB::table('assets')->whereRaw("{$length}(name) > ?", [191])->exists()) {
            throw new RuntimeException('Cannot narrow the asset name column while names exceed 191 characters.');
        }

        Schema::table('assets', function (Blueprint $table) {
            $table->string('name', 191)->nullable()->change();
        });
    }
};
