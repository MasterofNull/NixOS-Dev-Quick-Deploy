"""
Model optimization and advanced features HTTP handlers.

Extracted from http_server.py (Phase 12.4 decomposition).

All handlers delegate entirely to the `model_optimization` and
`advanced_features` modules via inline import; no coordinator state needed.
No init() required — zero injected dependencies.
"""

from aiohttp import web


async def handle_model_optimization_readiness(request: web.Request) -> web.Response:
    import model_optimization
    result = await model_optimization.get_optimization_readiness()
    return web.json_response(result)


async def handle_training_data_stats(request: web.Request) -> web.Response:
    import model_optimization
    result = await model_optimization.get_training_data_stats()
    return web.json_response(result)


async def handle_training_data_flush(request: web.Request) -> web.Response:
    import model_optimization
    result = await model_optimization.flush_training_data()
    return web.json_response(result)


async def handle_finetuning_jobs_list(request: web.Request) -> web.Response:
    import model_optimization
    status_filter = request.query.get("status")
    result = await model_optimization.get_finetuning_jobs(status_filter=status_filter)
    return web.json_response(result)


async def handle_finetuning_jobs_create(request: web.Request) -> web.Response:
    import model_optimization
    data = await request.json()
    result = await model_optimization.start_finetuning_job(
        base_model=data.get("base_model", ""),
        task_type=data.get("task_type", "general"),
        training_data_path=data.get("training_data_path"),
    )
    return web.json_response(result)


async def handle_model_performance(request: web.Request) -> web.Response:
    import model_optimization
    model_id = request.query.get("model_id")
    result = await model_optimization.get_model_performance(model_id=model_id)
    return web.json_response(result)


async def handle_synthetic_training_generate(request: web.Request) -> web.Response:
    import model_optimization
    data = await request.json()
    result = await model_optimization.generate_synthetic_training_data(
        target_examples=data.get("target_examples", 50),
        categories=data.get("categories"),
        strategies=data.get("strategies"),
        min_quality=data.get("min_quality", 0.7),
    )
    return web.json_response(result)


async def handle_active_learning_select(request: web.Request) -> web.Response:
    import model_optimization
    data = await request.json()
    result = await model_optimization.select_active_learning_examples(
        budget=data.get("budget", 25),
        strategy=data.get("strategy", "hybrid"),
        candidate_paths=data.get("candidate_paths"),
    )
    return web.json_response(result)


async def handle_distillation_pipeline_run(request: web.Request) -> web.Response:
    import model_optimization
    data = await request.json()
    result = await model_optimization.run_distillation_pipeline(
        teacher_model=data.get("teacher_model", ""),
        student_model=data.get("student_model", ""),
        training_data_path=data.get("training_data_path"),
        quantization_method=data.get("quantization_method", "gguf"),
        quantization_bits=data.get("quantization_bits", 4),
        pruning_sparsity=data.get("pruning_sparsity", 0.2),
        enable_speculative_decoding=data.get("enable_speculative_decoding", True),
    )
    return web.json_response(result)


async def handle_advanced_features_readiness(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_advanced_features_readiness()
    return web.json_response(result)


async def handle_advanced_agent_quality_profiles(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_agent_quality_profiles()
    return web.json_response(result)


async def handle_advanced_agent_failover_select(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.select_failover_remote_agent(
        min_composite_score=data.get("min_composite_score", 0.55),
    )
    return web.json_response(result)


async def handle_advanced_agent_benchmarks(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_agent_benchmarks()
    return web.json_response(result)


async def handle_advanced_prompt_optimize(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.optimize_prompt_template(
        task_type=data.get("task_type", "implementation"),
        task=data.get("task", ""),
        context=data.get("context"),
        constraints=data.get("constraints"),
    )
    return web.json_response(result)


async def handle_advanced_prompt_dynamic(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.generate_dynamic_prompt(
        query=data.get("query", ""),
        context=data.get("context"),
    )
    return web.json_response(result)


async def handle_advanced_prompt_ab_stats(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_prompt_ab_stats()
    return web.json_response(result)


async def handle_advanced_prompt_ab_record(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.record_prompt_variant_outcome(
        task_type=data.get("task_type", "implementation"),
        variant_id=data.get("variant_id", ""),
        score=data.get("score", 0.0),
    )
    return web.json_response(result)


async def handle_advanced_context_tier_select(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.select_context_tier(
        query=data.get("query", ""),
        context=data.get("context"),
    )
    return web.json_response(result)


async def handle_advanced_context_tier_stats(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_tier_selection_stats()
    return web.json_response(result)


async def handle_advanced_failure_patterns(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.analyze_failure_patterns(
        query=data.get("query", ""),
        response=data.get("response", ""),
        error_message=data.get("error_message"),
        user_feedback=data.get("user_feedback"),
    )
    return web.json_response(result)


async def handle_advanced_capability_gap_stats(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_capability_gap_stats()
    return web.json_response(result)


async def handle_advanced_learning_signal(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.record_learning_signal(
        query=data.get("query", ""),
        response=data.get("response", ""),
        outcome=data.get("outcome", "unknown"),
        explicit_score=data.get("explicit_score"),
    )
    return web.json_response(result)


async def handle_advanced_learning_recommendations(request: web.Request) -> web.Response:
    import advanced_features
    data = await request.json()
    result = await advanced_features.get_learning_recommendations(
        query=data.get("query", ""),
    )
    return web.json_response(result)


async def handle_advanced_learning_stats(request: web.Request) -> web.Response:
    import advanced_features
    result = await advanced_features.get_learning_stats()
    return web.json_response(result)


def register_routes(http_app: web.Application) -> None:
    # Model optimization
    http_app.router.add_get("/control/ai-coordinator/model-optimization/readiness", handle_model_optimization_readiness)
    http_app.router.add_get("/control/ai-coordinator/model-optimization/training-data/stats", handle_training_data_stats)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/training-data/flush", handle_training_data_flush)
    http_app.router.add_get("/control/ai-coordinator/model-optimization/finetuning/jobs", handle_finetuning_jobs_list)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/finetuning/jobs", handle_finetuning_jobs_create)
    http_app.router.add_get("/control/ai-coordinator/model-optimization/performance", handle_model_performance)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/synthetic-data/generate", handle_synthetic_training_generate)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/active-learning/select", handle_active_learning_select)
    http_app.router.add_post("/control/ai-coordinator/model-optimization/distillation/run", handle_distillation_pipeline_run)
    # Advanced features
    http_app.router.add_get("/control/ai-coordinator/advanced-features/readiness", handle_advanced_features_readiness)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/offloading/quality-profiles", handle_advanced_agent_quality_profiles)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/offloading/failover-select", handle_advanced_agent_failover_select)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/offloading/benchmarks", handle_advanced_agent_benchmarks)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/prompt/optimize", handle_advanced_prompt_optimize)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/prompt/dynamic", handle_advanced_prompt_dynamic)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/prompt/ab-stats", handle_advanced_prompt_ab_stats)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/prompt/ab-record", handle_advanced_prompt_ab_record)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/context/tier-select", handle_advanced_context_tier_select)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/context/tier-stats", handle_advanced_context_tier_stats)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/capability-gap/failure-patterns", handle_advanced_failure_patterns)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/capability-gap/stats", handle_advanced_capability_gap_stats)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/learning/signal", handle_advanced_learning_signal)
    http_app.router.add_post("/control/ai-coordinator/advanced-features/learning/recommendations", handle_advanced_learning_recommendations)
    http_app.router.add_get("/control/ai-coordinator/advanced-features/learning/stats", handle_advanced_learning_stats)
