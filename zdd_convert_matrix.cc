#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <unordered_map>
#include <string>
#include <set>

using namespace std;

struct ZDDNode {
    int var;      // 变量编号
    int hi_id;    // high child ID
    int lo_id;    // low child ID
    
    ZDDNode(int v, int hi, int lo) : var(v), hi_id(hi), lo_id(lo) {}
};

class ZDDMatrixConverter {
private:
    vector<ZDDNode> table_;
    unordered_map<int, int> id_convert_table_;
    vector<vector<int>> matrix_rows_;  // 存储矩阵的所有行
    
    static const int DD_ZERO_TERM = -1;  // 0终端节点
    static const int DD_ONE_TERM = -2;   // 1终端节点
    
public:
    /**
     * 从ZDD文件加载数据
     */
    void load_zdd_from_file(const string &file_name) {
        ifstream ifs(file_name);
        if (!ifs) {
            cerr << "无法打开文件 " << file_name << endl;
            return;
        }
        
        string line;
        while (getline(ifs, line)) {
            // 跳过注释行和空行
            if (line[0] == '.' || line[0] == '\n' || line[0] == '#' || line.size() == 0) 
                continue;
            
            istringstream iss(line);
            int nid, var;
            string lo_str, hi_str;
            int lo_id, hi_id;
            
            iss >> nid >> var >> lo_str >> hi_str;
            
            // 建立ID映射
            id_convert_table_[nid] = table_.size();
            
            // 处理low child
            if (lo_str[0] == 'B') {
                lo_id = DD_ZERO_TERM;
            } else if (lo_str[0] == 'T') {
                lo_id = DD_ONE_TERM;
            } else {
                lo_id = id_convert_table_[stoi(lo_str)];
            }
            
            // 处理high child
            if (hi_str[0] == 'B') {
                hi_id = DD_ZERO_TERM;
            } else if (hi_str[0] == 'T') {
                hi_id = DD_ONE_TERM;
            } else {
                hi_id = id_convert_table_[stoi(hi_str)];
            }
            
            table_.emplace_back(var, hi_id, lo_id);
        }
    }
    
    /**
     * 递归遍历ZDD，找到所有从根节点到T终端的路径
     * @param node_id 当前节点ID
     * @param current_path 当前路径上包含的列ID
     */
    void find_all_paths(int node_id, vector<int>& current_path) {
        // 如果到达1终端节点，记录当前路径
        if (node_id == DD_ONE_TERM) {
            matrix_rows_.push_back(current_path);
            return;
        }
        
        // 如果到达0终端节点，直接返回
        if (node_id == DD_ZERO_TERM) {
            return;
        }
        
        // 获取当前节点
        const ZDDNode& node = table_[node_id];
        
        // 走low边：不选择当前变量
        find_all_paths(node.lo_id, current_path);
        
        // 走high边：选择当前变量
        current_path.push_back(node.var);  // 将变量加入路径
        find_all_paths(node.hi_id, current_path);
        current_path.pop_back();  // 回溯
    }
    
    /**
     * 转换ZDD为矩阵并输出
     */
    void convert_to_matrix() {
        if (table_.empty()) {
            cout << "ZDD为空" << endl;
            return;
        }
        
        // 从最后一个节点开始（根节点）
        int root_id = table_.size() - 1;
        vector<int> initial_path;
        
        cout << "ZDD转换为矩阵表示：" << endl;
        cout << "每行显示该行包含的列ID：" << endl;
        cout << "========================" << endl;
        
        find_all_paths(root_id, initial_path);
        
        // 输出所有路径（矩阵行）
        for (int i = 0; i < matrix_rows_.size(); i++) {
            cout << "行 " << (i + 1) << ": ";
            if (matrix_rows_[i].empty()) {
                cout << "(空行)";
            } else {
                // 按升序排列列ID
                set<int> sorted_cols(matrix_rows_[i].begin(), matrix_rows_[i].end());
                bool first = true;
                for (int col : sorted_cols) {
                    if (!first) cout << " ";
                    cout << col;
                    first = false;
                }
            }
            cout << endl;
        }
        
        cout << "========================" << endl;
        cout << "总共 " << matrix_rows_.size() << " 行" << endl;
    }
    
    /**
     * 打印ZDD结构信息（调试用）
     */
    void print_zdd_structure() {
        cout << "\nZDD结构信息：" << endl;
        for (int i = 0; i < table_.size(); i++) {
            const ZDDNode& node = table_[i];
            cout << "节点[" << i << "]: var=" << node.var 
                 << ", lo=";
            if (node.lo_id == DD_ZERO_TERM) cout << "B";
            else if (node.lo_id == DD_ONE_TERM) cout << "T";
            else cout << node.lo_id;
            
            cout << ", hi=";
            if (node.hi_id == DD_ZERO_TERM) cout << "B";
            else if (node.hi_id == DD_ONE_TERM) cout << "T";
            else cout << node.hi_id;
            cout << endl;
        }
    }
};

int main() {
    ZDDMatrixConverter converter;
    
    // 这里假设ZDD数据已经以字符串形式给出
    // 在实际使用中，你可以从文件读取
    string zdd_data = R"(17 14 T T
3601635 13 17 17
3601630 13 B 17
3601631 13 T 17
3606324 12 3601630 3601630
3607955 12 3601635 3601635
3606325 12 3601631 3601630
3613676 11 3606324 3607955
3615327 11 3607955 3607955
3613677 11 3606325 3607955
3615333 10 3615327 3615327
3615328 10 3613676 3615327
3615329 10 3613677 3615327
3615335 9 3615333 3615333
3615331 9 3615329 3615328
3615339 8 3615335 3615335
3615337 8 3615331 3615335
3615341 7 3615337 3615339
3615345 6 3615341 3615341
3615349 5 3615345 3615345
3618617 4 3615349 3615349
3618619 3 3618617 3618617
3619407 2 3618619 3618619
3619409 1 3619407 3619407)";
    
    // 将数据写入临时文件
    ofstream temp_file("temp_zdd.txt");
    temp_file << zdd_data;
    temp_file.close();
    
    // 加载并转换ZDD
    converter.load_zdd_from_file("temp_zdd.txt");
    converter.print_zdd_structure();
    converter.convert_to_matrix();
    
    return 0;
}