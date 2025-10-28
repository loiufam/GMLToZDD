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
                                   bool verbose = true) {
    ProcessingResult result;
    result.filename = fs::path(input_path).stem().string();
    result.success = false;
    result.nodes = 0;
    result.edges = 0;
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    try {
        std::cout << "  处理文件: " << result.filename << std::endl;
        
        // 创建MyTdZdd对象
        MyTdZdd mytdzdd(input_path.c_str());
        
        // 获取图的基本信息
        result.nodes = mytdzdd.getGraph().getNumOfV(); 
        result.edges = mytdzdd.getGraph().getNumOfE();   
        
        // 执行计算
        if (verbose) {
            MyEval result_eval = mytdzdd.Connected(IntSubset({1}));
            // 保存ZDD结果到Matrix文件  
            result_eval.dump(std::cout);
            result_eval.dumpMatrix(output_path.c_str());
        } else {
            mytdzdd.EnumCycle(output_path.c_str());
        }

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
std::vector<ProcessingResult> batchProcessFolder(const std::string& input_folder, bool verbose = true, int max_process_num = 100) {
    
    std::vector<ProcessingResult> results;
    
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
    } else {
        std::cout << "在文件夹 " << input_folder << " 中找到 " << in_files.size() << " 个.in文件" << std::endl;
    }
    
    // 将编译时间写入文件
    std::ofstream compile_time_file("./gml_compile_to_matrix_time.txt", std::ios::app);

    std::string file_path_prefix;
    if (verbose) {
        file_path_prefix = "./partition_set";
    } else {
        file_path_prefix = "./cycle_set";
    }

    // 处理每个文件
    for (size_t i = 0; i < in_files.size(); ++i) {
        const std::string& input_path = in_files[i];
        
        // 生成输出文件名
        fs::path input_file_path(input_path);
        std::string output_filename = input_file_path.stem().string() + ".txt";
        std::string output_path = (fs::path(file_path_prefix) / output_filename).string();
        
        std::cout << "[" << (i + 1) << "/" << in_files.size() << "] ";
        
        auto start_time = std::chrono::high_resolution_clock::now();
        ProcessingResult result = processSingleFile(input_path, output_path, verbose);
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
    std::cout << "    " << program_name << " <input.in> [enum_type] " << std::endl;
    std::cout << "    例如: " << program_name << " network.in p/c " << std::endl;
    std::cout << std::endl;
    std::cout << "  批量文件夹处理:" << std::endl;
    std::cout << "    " << program_name << " -b <input_folder> [enum_type] " << std::endl;
    std::cout << "    例如: " << program_name << " -b ./in_files p/c " << std::endl;
    std::cout << std::endl;
}

int main(int argc, char* argv[]) {
	
	if (argc < 3) {
        showHelp(argv[0]);
        return 1;
    }
    
    // 检查是否为批量处理模式
    if (std::string(argv[1]) == "-b") {
        if (argc < 4) {
            std::cout << "批量处理模式需要指定输入和枚举类型" << std::endl;
            showHelp(argv[0]);
            return 1;
        }
        
        std::string input_folder = argv[2];
        bool verbose = std::string(argv[3]) == "p";
        
        // 检查输入文件夹是否存在
        if (!fs::exists(input_folder) || !fs::is_directory(input_folder)) {
            std::cout << "输入文件夹不存在或不是目录: " << input_folder << std::endl;
            return 1;
        }
        
        // 执行批量处理
        auto results = batchProcessFolder(input_folder, verbose);
        printStatistics(results);
        
    } else {
        // 执行单个文件转换
        std::string input_file = argv[1];
        bool verbose = std::string(argv[2]) == "p";

        std::cout << "正在转换文件: " << input_file << std::endl;
        std::cout << "枚举类型: " << (verbose ? "Partition" : "Cycle") << std::endl;

        std::string output_file = "./output/" + fs::path(input_file).stem().string() + ".txt";
        // 执行转换
        auto result = processSingleFile(input_file, output_file, verbose);
    
    }
    
    return 0;
}
