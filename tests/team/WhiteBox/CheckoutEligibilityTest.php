<?php

namespace Tests\team\WhiteBox;

use App\Models\Asset;
use App\Models\Statuslabel;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class CheckoutEligibilityTest extends TestCase
{
    public static function checkoutDecisions(): iterable
    {
        foreach ([false, true] as $unassigned) {
            foreach ([false, true] as $undeleted) {
                foreach (['missing', 'pending', 'ready', 'archived', 'conflicting'] as $status) {
                    $key = sprintf('%s/%s/%s', $unassigned ? 'unassigned' : 'assigned', $undeleted ? 'live' : 'deleted', $status);
                    yield $key => [$unassigned, $undeleted, $status, $key === 'unassigned/live/ready'];
                }
            }
        }
    }

    #[DataProvider('checkoutDecisions')]
    public function test_checkout_decision_for_each_distinguishable_state(
        bool $unassigned,
        bool $undeleted,
        string $status,
        bool $expected
    ): void {
        $asset = new Asset;
        $asset->setDateFormat('Y-m-d H:i:s');
        $asset->assigned_to = $unassigned ? null : 17;
        $asset->deleted_at = $undeleted ? null : '2025-01-01 10:00:00';
        $asset->setRelation('status', $status === 'missing' ? null : new Statuslabel([
            'archived' => (int) in_array($status, ['archived', 'conflicting'], true),
            'deployable' => (int) in_array($status, ['ready', 'conflicting'], true),
        ]));

        $this->assertSame($expected, $asset->availableForCheckout());
    }
}
