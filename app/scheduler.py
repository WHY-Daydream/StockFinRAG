"""定时任务调度器"""
from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger


scheduler = BackgroundScheduler(daemon=True)


def init_scheduler(app):
    """初始化定时任务（在 Flask 启动时调用）"""
    if not app.config.get("SCHEDULER_ENABLED", True):
        logger.info("Scheduler disabled by config")
        return

    # 指数行情更新 — 工作日 9:00 和 15:00
    @scheduler.scheduled_job("cron", day_of_week="mon-fri", hour=9, minute=0, id="indices_morning")
    def update_indices_morning():
        _run_update_indices()

    @scheduler.scheduled_job("cron", day_of_week="mon-fri", hour=15, minute=0, id="indices_evening")
    def update_indices_evening():
        _run_update_indices()

    # 财经新闻 — 每小时（通过 AKShare 获取今日最新新闻）
    @scheduler.scheduled_job("interval", hours=1, id="fetch_news")
    def fetch_news():
        logger.info("[Scheduler] Fetching latest financial news...")
        try:
            from data_providers.akshare_provider import fetch_latest_news, save_news
            news = fetch_latest_news(limit=10)
            if news:
                saved = save_news(news)
                logger.info(f"[Scheduler] Saved {saved} new news articles")
                if saved > 0:
                    _run_vectorize()
            else:
                logger.info("[Scheduler] No new news")
        except Exception as e:
            logger.error(f"[Scheduler] News fetch failed: {e}")

    # 网页爬虫 — 每 6 小时（发现模式，获取政策法规更新）
    @scheduler.scheduled_job("interval", hours=6, id="crawl_web")
    def crawl_web():
        logger.info("[Scheduler] Starting web crawl...")
        try:
            from crawler.financial_crawler import batch_crawl
            ids = batch_crawl()
            logger.info(f"[Scheduler] Crawled {len(ids)} new documents")
            if ids:
                _run_vectorize()
        except Exception as e:
            logger.error(f"[Scheduler] Crawl failed: {e}")

    # 政策检查 — 每周一 8:00
    @scheduler.scheduled_job("cron", day_of_week="mon", hour=8, minute=0, id="policy_check")
    def check_policy():
        logger.info("[Scheduler] Starting policy check...")
        try:
            from crawler.financial_crawler import batch_crawl
            ids = batch_crawl()
            logger.info(f"[Scheduler] Policy check: {len(ids)} new documents")
        except Exception as e:
            logger.error(f"[Scheduler] Policy check failed: {e}")

    # 宏观经济数据（每天 9:30）
    def fetch_macro():
        logger.info("Scheduler: fetching macro data...")
        from data_providers.akshare_provider import fetch_macro_gdp, fetch_macro_cpi
        from retrieval.cache import ResultCache
        import json
        cache = ResultCache()
        try:
            gdp = fetch_macro_gdp()
            if gdp:
                cache.redis.setex("macro:gdp", 86400, json.dumps(gdp, ensure_ascii=False))
            cpi = fetch_macro_cpi()
            if cpi:
                cache.redis.setex("macro:cpi", 86400, json.dumps(cpi, ensure_ascii=False))
            logger.info(f"Macro data updated: {len(gdp)} GDP, {len(cpi)} CPI")
        except Exception as e:
            logger.error(f"fetch_macro failed: {e}")

    scheduler.add_job(fetch_macro, "cron", hour=9, minute=30, id="sched_macro", replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started with {} jobs".format(len(scheduler.get_jobs())))


def _run_update_indices():
    """更新指数行情"""
    logger.info("[Scheduler] Updating stock indices...")
    try:
        from data_providers.akshare_provider import update_all_indices
        total = update_all_indices()
        logger.info(f"[Scheduler] Indices updated: {total} new records")
    except Exception as e:
        logger.error(f"[Scheduler] Index update failed: {e}")


def _run_vectorize():
    """处理未向量化的文档"""
    logger.info("[Scheduler] Vectorizing unprocessed docs...")
    try:
        from ingestion.pipeline import FinKnowledgeBuilder
        builder = FinKnowledgeBuilder()
        count = builder.process_unprocessed_docs(limit=20)
        logger.info(f"[Scheduler] Vectorized {count} documents")
    except Exception as e:
        logger.error(f"[Scheduler] Vectorization failed: {e}")