==========
Containers
==========

.. automodule:: teststack.commands.containers
    :members:

    .. autofunction:: start(ctx, no_tests)
    .. autofunction:: stop(ctx)
    .. autofunction:: restart(ctx)
    .. autofunction:: render(ctx, template_file, dockerfile)
    .. autofunction:: build(ctx, rebuild, tag, dockerfile)
    .. autofunction:: exec(ctx)
    .. autofunction:: run(ctx, step, posargs)
    .. autofunction:: import_(ctx, repo, ref, stop)
