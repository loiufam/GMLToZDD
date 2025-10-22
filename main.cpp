#include "MyTdZdd.hpp"
using namespace tdzdd;
using namespace hybriddd;

#include <iostream>
#include <filesystem>
#include <string>
#include <vector>
#include <chrono>
#include <iomanip>

namespace fs = std::filesystem;

struct ProcessingResult {
    std::string filename;
    bool success;
    std::string error_message;
    int nodes;
    int edges;
    double processing_time_ms;
};

// 处理单个.in文件
ProcessingResult processSingleFile(const std::string& input_path, const std::string& output_path, 
                                   int source = 0, int target = 4, bool verbose = false) {
    ProcessingResult result;
    result.filename = fs::path(input_path).filename().string();
    result.success = false;
    result.nodes = 0;
    result.edges = 0;
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    try {
        if (verbose) {
            std::cout << "  处理文件: " << result.filename << std::endl;
        }
        
        // 创建MyTdZdd对象
        MyTdZdd mytdzdd(input_path.c_str(), "as-is");
        
        // 获取图的基本信息
        result.nodes = mytdzdd.getGraph().getNumOfV(); 
        result.edges = mytdzdd.getGraph().getNumOfE();   
        
        // 执行S-T路径计算
        MyEval path_result = mytdzdd.S_T_Path(source, target, true);
        
        if (verbose) {
            // 输出图的结构信息
            int I = mytdzdd.getGraph().getNumOfI();
            std::cout << "    图结构信息:" << std::endl;
            for (int i = 0; i < I; ++i) {
                HybridGraph::Item item = mytdzdd.getGraph().getItemAf(i);
                std::cout << "    Lev." << I - i << " : ";
                if (item.isvertex) std::cout << "v" << item.v << std::endl;
                else std::cout << "e={v" << item.v1 << ", v" << item.v2 << "}" << std::endl;
            }
            
            // 输出结果到控制台
            std::cout << "    ZDD结果:" << std::endl;
            path_result.dump(std::cout);
        }
        
        // 保存ZDD结果到文件
        path_result.dumpSapporo(output_path.c_str());
        
        result.success = true;
        
    } catch (const std::exception& e) {
        result.error_message = e.what();
    } catch (...) {
        result.error_message = "未知错误";
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    result.processing_time_ms = duration.count();
    
    return result;
}

// 批量处理文件夹
std::vector<ProcessingResult> batchProcessFolder(const std::string& input_folder, 
                                                const std::string& output_folder,
                                                int source = 0, int target = 4, 
                                                bool verbose = false) {
    std::vector<ProcessingResult> results;
    
    // 确保输出文件夹存在
    if (!fs::exists(output_folder)) {
        fs::create_directories(output_folder);
        std::cout << "创建输出文件夹: " << output_folder << std::endl;
    }
    
    // 查找所有.in文件
    std::vector<std::string> in_files;
    for (const auto& entry : fs::directory_iterator(input_folder)) {
        if (entry.is_regular_file() && entry.path().extension() == ".in") {
            in_files.push_back(entry.path().string());
        }
    }
    
    if (in_files.empty()) {
        std::cout << "在文件夹 " << input_folder << " 中未找到任何.in文件" << std::endl;
        return results;
    }
    
    std::cout << "找到 " << in_files.size() << " 个.in文件" << std::endl;
    std::cout << "源节点: " << source << ", 目标节点: " << target << std::endl;
    std::cout << std::string(60, '-') << std::endl;
    
    // 将编译时间写入文件
    std::ofstream compile_time_file("./zdd_compile_time.txt", std::ios::app);

    // 处理每个文件
    for (size_t i = 0; i < in_files.size(); ++i) {
        const std::string& input_path = in_files[i];
        
        // 生成输出文件名
        fs::path input_file_path(input_path);
        std::string output_filename = input_file_path.stem().string() + ".zdd";
        std::string output_path = (fs::path(output_folder) / output_filename).string();
        
        std::cout << "[" << (i + 1) << "/" << in_files.size() << "] ";
        
        auto start_time = std::chrono::high_resolution_clock::now();
        ProcessingResult result = processSingleFile(input_path, output_path, source, target, verbose);
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);

        results.push_back(result);
        
        if (result.success) {
            // 写入文件
            compile_time_file << result.filename << ": " << duration.count() << " 毫秒" << std::endl;
            std::cout << "✓ " << result.filename << " -> " << output_filename;
            std::cout << " (" << std::fixed << std::setprecision(2) << result.processing_time_ms << "ms)" << std::endl;
        } else {
            compile_time_file << result.filename << ": 编译错误" << std::endl;
            std::cout << "✗ " << result.filename << " - 错误: " << result.error_message << std::endl;
        }
    }
    
    return results;
}

// 打印统计信息
void printStatistics(const std::vector<ProcessingResult>& results) {
    std::cout << std::string(60, '=') << std::endl;
    std::cout << "批量处理完成!" << std::endl;
    
    int successful = 0;
    int failed = 0;
    double total_time = 0;
    
    for (const auto& result : results) {
        if (result.success) {
            successful++;
        } else {
            failed++;
        }
        total_time += result.processing_time_ms;
    }
    
    std::cout << "成功处理: " << successful << " 个文件" << std::endl;
    std::cout << "处理失败: " << failed << " 个文件" << std::endl;
    std::cout << "总耗时: " << std::fixed << std::setprecision(2) << total_time / 1000.0 << " 秒" << std::endl;
    
    if (failed > 0) {
        std::cout << "\n失败的文件:" << std::endl;
        for (const auto& result : results) {
            if (!result.success) {
                std::cout << "  " << result.filename << " - " << result.error_message << std::endl;
            }
        }
    }
}

// 显示帮助信息
void showHelp(const char* program_name) {
    std::cout << "使用方法:" << std::endl;
    std::cout << "  单文件处理:" << std::endl;
    std::cout << "    " << program_name << " <input.in> [source] [target]" << std::endl;
    std::cout << "    例如: " << program_name << " network.in 0 4" << std::endl;
    std::cout << std::endl;
    std::cout << "  批量文件夹处理:" << std::endl;
    std::cout << "    " << program_name << " --batch <input_folder> <output_folder> [source] [target] [--verbose]" << std::endl;
    std::cout << "    例如: " << program_name << " --batch ./in_files ./zdd_files 0 4" << std::endl;
    std::cout << std::endl;
    std::cout << "参数说明:" << std::endl;
    std::cout << "  source  : 源节点ID (默认: 0)" << std::endl;
    std::cout << "  target  : 目标节点ID (默认: 4)" << std::endl;
    std::cout << "  --verbose : 显示详细处理信息" << std::endl;
}

// 将graph.in转换为graph.zdd
int main(int argc, char* argv[]) {
	
	if (argc < 2) {
        showHelp(argv[0]);
        return 1;
    }
    
    // 检查是否为批量处理模式
    if (std::string(argv[1]) == "--batch") {
        if (argc < 4) {
            std::cout << "批量处理模式需要指定输入和输出文件夹" << std::endl;
            showHelp(argv[0]);
            return 1;
        }
        
        std::string input_folder = argv[2];
        std::string output_folder = argv[3];
        int source = (argc > 4) ? std::stoi(argv[4]) : 0;
        int target = (argc > 5) ? std::stoi(argv[5]) : 4;
        bool verbose = false;
        
        // 检查是否有--verbose参数
        for (int i = 6; i < argc; ++i) {
            if (std::string(argv[i]) == "--verbose") {
                verbose = true;
                break;
            }
        }
        
        // 检查输入文件夹是否存在
        if (!fs::exists(input_folder) || !fs::is_directory(input_folder)) {
            std::cout << "输入文件夹不存在或不是目录: " << input_folder << std::endl;
            return 1;
        }
        
        // 执行批量处理
        auto results = batchProcessFolder(input_folder, output_folder, source, target, verbose);
        printStatistics(results);
        
    } else {
        // 单文件处理模式（保持原有功能）
        std::string input_file = argv[1];
        int source = (argc > 2) ? std::stoi(argv[2]) : 0;
        int target = (argc > 3) ? std::stoi(argv[3]) : 4;
        
        try {
            MyTdZdd mytdzdd(input_file.c_str(), "as-is");

            MyEval result = mytdzdd.S_T_Path(source, target, true);
            
            int I = mytdzdd.getGraph().getNumOfI();
            for (int i = 0; i < I; ++i) {
                HybridGraph::Item item = mytdzdd.getGraph().getItemAf(i);
                std::cout << "Lev." << I - i << " : ";
                if (item.isvertex) std::cout << "v" << item.v << std::endl;
                else std::cout << "e={v" << item.v1 << ", v" << item.v2 << "}" << std::endl;
            }
            
            result.dump(std::cout);
            
            // 生成输出文件名
            fs::path input_path(input_file);
            std::string output_filename = input_path.stem().string() + ".zdd";
            result.dumpSapporo(output_filename.c_str());
            
            std::cout << "结果已保存到: " << output_filename << std::endl;
            
        } catch (const std::exception& e) {
            std::cout << "处理文件时出错: " << e.what() << std::endl;
            return 1;
        }
    }
    
    return 0;
}
