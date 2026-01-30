.PHONY: install test test-unit test-integration lint format run clean help

help:  ## 显示帮助信息
	@echo "可用的命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## 安装依赖
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:  ## 运行所有测试
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

test-unit:  ## 运行单元测试
	pytest tests/unit/ -v --cov=src

test-integration:  ## 运行集成测试
	pytest tests/integration/ -v

lint:  ## 代码检查
	@echo "Running black formatter check..."
	black --check src/ tests/
	@echo "Running ruff linter..."
	ruff check src/ tests/
	@echo "Running mypy type checker..."
	mypy src/

format:  ## 格式化代码
	black src/ tests/
	ruff check --fix src/ tests/

run:  ## 运行示例 (需要参数 ARGS="描述")
	python -m src.cli diagnose $(ARGS)

clean:  ## 清理临时文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	rm -rf runtime/reports/* runtime/logs/*
	@echo "清理完成!"

setup-dev:  ## 设置开发环境 (创建虚拟环境并安装依赖)
	python -m venv venv
	@echo "请运行: source venv/bin/activate (Linux/Mac) 或 venv\\Scripts\\activate (Windows)"
	@echo "然后运行: make install"
