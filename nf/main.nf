#!/usr/bin/env nextflow

/*
 * 主 Nextflow 工作流入口
 *
 * 该文件可以根据 --tool 参数调用不同的工具模块
 */

nextflow.enable.dsl = 2

params.tool = null

workflow {
    if (params.tool == null) {
        error "ERROR: --tool parameter is required. Use --tool <tool_name>"
    }

    println "Executing tool: ${params.tool}"
}
