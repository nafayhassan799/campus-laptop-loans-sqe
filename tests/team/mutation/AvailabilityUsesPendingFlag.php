<?php

namespace Sqe\Mutation;

use Infection\Mutator\Definition;
use Infection\Mutator\Mutator;
use Infection\Mutator\MutatorCategory;
use PhpParser\Node;
use PhpParser\Node\Expr\PropertyFetch;
use PhpParser\Node\Expr\Variable;
use PhpParser\Node\Identifier;

final class AvailabilityUsesPendingFlag implements Mutator
{
    public function canMutate(Node $node): bool
    {
        return $node instanceof PropertyFetch
            && $node->name instanceof Identifier
            && $node->name->toString() === 'deployable'
            && $node->var instanceof PropertyFetch
            && $node->var->name instanceof Identifier
            && $node->var->name->toString() === 'status'
            && $node->var->var instanceof Variable
            && $node->var->var->name === 'this';
    }

    public function mutate(Node $node): iterable
    {
        $changed = clone $node;
        $changed->name = new Identifier('pending');
        yield $changed;
    }

    public static function getDefinition(): Definition
    {
        return new Definition(
            'Use the pending flag when checking asset availability.',
            MutatorCategory::ORTHOGONAL_REPLACEMENT,
            'Exercise the deployable and pending status labels in separate cases.',
            '$this->status->deployable becomes $this->status->pending',
        );
    }

    public function getName(): string
    {
        return self::class;
    }
}
