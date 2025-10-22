#include <iostream>
#include <fstream>
#include <vector>
#include <set>
#include <string>
#include <filesystem>
#include <sstream>

namespace fs = std::filesystem;

class GraphConverter {
private:
    std::vector<std::set<int>> adjacencyList;
    int nodeCount;
    int edgeCount;

public:
    bool parseGraphFile(const std::string& inputFile) {
        std::ifstream file(inputFile);
        if (!file.is_open()) {
            std::cerr << "Error: Cannot open file " << inputFile << std::endl;
            return false;
        }

        std::string line;
        bool firstLine = true;
        
        while (std::getline(file, line)) {
            std::istringstream iss(line);
            
            if (firstLine) {
                // 解析第一行：节点数和边数
                iss >> nodeCount >> edgeCount;
                adjacencyList.resize(nodeCount);
                firstLine = false;
            } else {
                // 解析边信息
                int node1, node2;
                if (iss >> node1 >> node2) {
                    // 添加无向边
                    adjacencyList[node1].insert(node2);
                    adjacencyList[node2].insert(node1);
                }
            }
        }
        
        file.close();
        return true;
    }

    bool writeMatrixFile(const std::string& outputFile) {
        std::ofstream file(outputFile);
        if (!file.is_open()) {
            std::cerr << "Error: Cannot create output file " << outputFile << std::endl;
            return false;
        }

        // 写入矩阵维度（cols rows）
        file << nodeCount << " " << nodeCount << std::endl;

        // 写入每行的邻接信息
        for (int i = 0; i < nodeCount; i++) {
            file << adjacencyList[i].size(); // 该行的列数（邻接节点数）
            
            // 写入邻接节点
            for (int neighbor : adjacencyList[i]) {
                file << " " << neighbor + 1; // 转换为1-based索引
            }
            file << std::endl;
        }

        file.close();
        return true;
    }

    void clear() {
        adjacencyList.clear();
        nodeCount = 0;
        edgeCount = 0;
    }

    void printGraphInfo() const {
        std::cout << "Graph Info: " << nodeCount << " nodes, " << edgeCount << " edges" << std::endl;
        std::cout << "Adjacency List:" << std::endl;
        for (int i = 0; i < nodeCount; i++) {
            std::cout << "Node " << i << ": ";
            for (int neighbor : adjacencyList[i]) {
                std::cout << neighbor << " ";
            }
            std::cout << std::endl;
        }
    }
};

void convertSingleFile(const std::string& inputFile, const std::string& outputFile, bool skipExisting = true) {
    // 检查输出文件是否已存在
    if (skipExisting && fs::exists(outputFile)) {
        std::cout << "Skipping " << inputFile << " - output file already exists" << std::endl;
        return;
    }

    GraphConverter converter;
    
    std::cout << "Processing: " << inputFile << std::endl;
    
    if (!converter.parseGraphFile(inputFile)) {
        std::cerr << "Failed to parse file: " << inputFile << std::endl;
        return;
    }

    if (!converter.writeMatrixFile(outputFile)) {
        std::cerr << "Failed to write output file: " << outputFile << std::endl;
        return;
    }

    std::cout << "Successfully converted: " << inputFile << " -> " << outputFile << std::endl;
}

void batchConvert(const std::string& inputDir, const std::string& outputDir, const std::string& fileExtension = ".txt") {
    // 创建输出目录（如果不存在）
    if (!fs::exists(outputDir)) {
        fs::create_directories(outputDir);
    }

    int processedCount = 0;
    int skippedCount = 0;

    // 遍历输入目录中的所有文件
    for (const auto& entry : fs::directory_iterator(inputDir)) {
        if (entry.is_regular_file()) {
            std::string inputFile = entry.path().string();
            std::string filename = entry.path().filename().string();
            
            // 构造输出文件路径
            std::string outputFile = outputDir + "/" + filename + ".txt";
            
            // 检查输出文件是否已存在
            if (fs::exists(outputFile)) {
                std::cout << "Skipping " << filename << " - output file already exists" << std::endl;
                skippedCount++;
                continue;
            }

            convertSingleFile(inputFile, outputFile, false);
            processedCount++;
        }
    }

    std::cout << "\nBatch conversion completed!" << std::endl;
    std::cout << "Processed: " << processedCount << " files" << std::endl;
    std::cout << "Skipped: " << skippedCount << " files" << std::endl;
}

int main(int argc, char** argv) {
    std::cout << "Graph Edge to Matrix Converter" << std::endl;
    std::cout << "================================" << std::endl;
    std::cout << "Usage: gml_to_matrix [options] <input> <output>" << std::endl;

    if (argc < 4) {
        std::cout << "Options:" << std::endl;
        std::cout << "  --s <input_file> <output_file>   Convert a single file" << std::endl;
        std::cout << "  --b <input_dir> <output_dir>     Batch convert all files in a directory" << std::endl;
        return 1;
    }

    if (std::string(argv[1]) == "--s") {
        // 单文件转换模式
        std::string inputFile = argv[2], outputFile = argv[3];
        
        convertSingleFile(inputFile, outputFile);
    }
    else if (std::string(argv[1]) == "--b") {
        // 批量转换模式
        std::string inputDir = argv[2], outputDir = argv[3];
     
        batchConvert(inputDir, outputDir);
    }
    else {
        std::cout << "无效的选择!" << std::endl;
        return 1;
    }

    return 0;
}

    