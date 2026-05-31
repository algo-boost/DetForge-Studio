"""
Dataset Downloader Script (CLI Version)
Downloads dataset snapshots from the API by providing dataset ID as parameter.
"""

import argparse
import copy
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm


def _direct_proxies() -> dict:
    """直连 API，不使用环境变量/系统代理（避免本机代理异常导致 ProxyError）。"""
    return {"http": None, "https": None}


def _api_session() -> requests.Session:
    """不信任 HTTP(S)_PROXY 环境变量与系统代理 discovery（与 _direct_proxies 一起避免 ProxyError）。"""
    s = requests.Session()
    s.trust_env = False
    return s


# API Configuration
DEFAULT_FORMAT = "coco"


def load_api_credentials():
    """Load API credentials and optional category groups from .config."""
    config_path = Path(__file__).resolve().parent / ".config"
    if not config_path.exists():
        raise FileNotFoundError(".config 文件不存在，请在脚本同级目录创建该文件。")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(".config 文件内容不是有效的 JSON。") from exc

    required_fields = ["base_url", "username", "password"]
    missing = [field for field in required_fields if field not in data or not data[field]]
    if missing:
        raise ValueError(f".config 缺少必要字段: {', '.join(missing)}")

    category_groups = {}
    raw_groups = data.get("category_groups") or {}
    if raw_groups and not isinstance(raw_groups, dict):
        raise ValueError("category_groups 必须为字典类型。")

    for group_name, mapping in raw_groups.items():
        if not isinstance(mapping, dict):
            raise ValueError(f"类别组 {group_name} 必须是字典。")
        parsed_mapping = {}
        for key, value in mapping.items():
            if not isinstance(value, str):
                raise ValueError(f"类别组 {group_name} 的值必须为字符串。")
            try:
                parsed_key = int(key)
            except (TypeError, ValueError):
                raise ValueError(f"类别组 {group_name} 的键必须为整数或可转换为整数的字符串。")
            parsed_mapping[parsed_key] = value
        category_groups[group_name] = parsed_mapping

    return data["base_url"], data["username"], data["password"], category_groups


def rename_coco_imgnames(current_dir: Path):
    """重命名COCO标注文件中的图片文件名，移除前缀。"""
    coco_fp = current_dir / "_annotations.coco.json"
    if not coco_fp.exists():
        raise FileNotFoundError(f"未找到 COCO 标注文件: {coco_fp}")

    with open(coco_fp, 'r', encoding='utf-8') as f:
        coco_data = json.load(f)

    images = coco_data.get('images', [])
    for image in images:
        file_name = image.get('file_name')
        if not file_name:
            continue

        parts = file_name.split('_')
        if len(parts) < 2:
            continue

        new_file_name = "_".join(parts[1:])
        if not new_file_name or new_file_name == file_name:
            continue

        src = current_dir / file_name
        dst = current_dir / new_file_name

        if not src.exists():
            raise FileNotFoundError(f"待重命名的文件不存在: {src}")

        if dst.exists():
            dst.unlink()

        shutil.move(src, dst)
        image['file_name'] = new_file_name

    with open(coco_fp, 'w', encoding='utf-8') as f:
        json.dump(coco_data, f, indent=4, ensure_ascii=False)


def remap_coco_categories(coco_path: Path, output_path: Path, model_id2name):
    """
    将coco标注文件的categories和annotations中的类别id映射到模型的id，并补全缺失的类别
    :param coco_path: 原始coco json文件路径
    :param output_path: 修正后的coco json文件保存路径
    :param model_id2name: 模型的id2name字典，例如 {0: "cat", 1: "dog", ...}
    """
    with open(coco_path, "r", encoding="utf-8") as f:
        coco = json.load(f)

    coco_name2id = {cat['name']: cat['id'] for cat in coco.get('categories', [])}
    coco_id2name = {cat['id']: cat['name'] for cat in coco.get('categories', [])}

    model_name2id = {v: k for k, v in model_id2name.items()}

    catid_map = {}
    for coco_id, name in coco_id2name.items():
        if name in model_name2id:
            catid_map[coco_id] = model_name2id[name]

    new_annotations = []
    for ann in coco.get('annotations', []):
        old_cat = ann.get('category_id')
        if old_cat in catid_map:
            ann_new = copy.deepcopy(ann)
            ann_new['category_id'] = catid_map[old_cat]
            new_annotations.append(ann_new)

    new_categories = []
    for model_id, name in model_id2name.items():
        new_categories.append({
            "id": model_id,
            "name": name,
            "supercategory": "none"
        })

    new_coco = copy.deepcopy(coco)
    new_coco['categories'] = new_categories
    new_coco['annotations'] = new_annotations

    if output_path.exists():
        output_path.unlink()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(new_coco, f, ensure_ascii=False, indent=2)


def login_and_get_token(base_url: str, username: str, password: str, logger=None):
    """登录并获取访问令牌。"""
    log = logger or (lambda msg: print(msg))
    log("=== Step 1: 登录并获取 Token ===")
    
    login_url = f"{base_url}/login/access-token"
    login_data = {
        "username": username,
        "password": password,
        "scope": "",
        "client_id": "",
        "client_secret": ""
    }
    
    try:
        with _api_session() as s:
            response = s.post(login_url, data=login_data, proxies=_direct_proxies())
        if response.status_code == 200:
            token_data = response.json()
            if "access_token" in token_data:
                token = token_data["access_token"]
                log(f"✅ 登录成功，Token: {token[:50]}...")
                return token
            else:
                log("❌ 响应中未找到 access_token")
                return None
        else:
            log(f"❌ 登录失败，状态码: {response.status_code}")
            log(f"响应内容: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        log(f"❌ 登录请求异常: {e}")
        return None


def export_dataset_snapshot(base_url: str, token: str, dataset_id: str, export_format: str, logger=None):
    """导出数据集快照。"""
    log = logger or (lambda msg: print(msg))
    log(f"\n=== Step 2: 导出数据集快照 {dataset_id} ===")
    
    export_url = f"{base_url}/datasets/export_snapshot/{dataset_id}?format={export_format}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    s = _api_session()
    response = None
    try:
        response = s.post(export_url, headers=headers, data="", stream=True, proxies=_direct_proxies())

        log(f"请求 URL: {export_url}")
        log(f"响应状态: {response.status_code}")
        log(f"响应 Content-Type: {response.headers.get('content-type', 'N/A')}")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                try:
                    json_data = response.json()
                    log("✅ 收到 JSON 响应：")
                    log(json.dumps(json_data, indent=2, ensure_ascii=False))
                    
                    if json_data is None:
                        log("⚠️ 响应为空，任务可能仍在处理中")
                        return None
                        
                    if isinstance(json_data, dict):
                        download_url = json_data.get('download_url') or json_data.get('url') or json_data.get('file_url')
                        if download_url:
                            log(f"🔗 找到下载链接: {download_url}")
                            return download_url
                        
                        task_id = json_data.get('task_id') or json_data.get('job_id') or json_data.get('export_id')
                        if task_id:
                            log(f"🔄 找到任务 ID: {task_id}")
                            log("这是一个异步任务，正在轮询状态...")
                            return poll_task_status(base_url, token, task_id, logger)
                        
                        if 'status' in json_data:
                            log(f"📊 任务状态: {json_data['status']}")
                        if 'message' in json_data:
                            log(f"💬 消息: {json_data['message']}")
                            
                    return None
                    
                except json.JSONDecodeError:
                    log("❌ JSON 解析失败")
                    return None
                    
            elif any(file_type in content_type for file_type in ['application/zip', 'application/octet-stream', 'application/x-zip-compressed']):
                log("✅ 收到文件数据，正在保存...")
                filename = f"dataset_{dataset_id}_{export_format}.zip"
                try:
                    total_size = int(response.headers.get('content-length', 0)) or None
                    with open(filename, 'wb') as f, tqdm(total=total_size, unit='B', unit_scale=True, desc="下载中") as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                    file_size = os.path.getsize(filename)
                    log(f"✅ 文件已保存: {filename}")
                    log(f"📊 文件大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                    log(f"📁 保存路径: {os.path.abspath(filename)}")
                    return Path(filename)
                except Exception as e:
                    log(f"❌ 保存文件失败: {e}")
                    return None
                
            else:
                log(f"⚠️ 未知响应类型: {content_type}")
                log(f"响应内容（前 500 字符）: {response.text[:500]}")
                return None
                
        elif response.status_code == 401:
            log("❌ 认证失败，Token 可能已失效")
            return None
            
        elif response.status_code == 404:
            log(f"❌ 数据集 {dataset_id} 未找到或 API 路径错误")
            return None
            
        elif response.status_code == 400:
            log("❌ 请求参数错误")
            log(f"响应: {response.text}")
            return None
            
        else:
            log(f"❌ 请求失败，状态码: {response.status_code}")
            log(f"响应: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        log(f"❌ 请求异常: {e}")
        return None
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        s.close()


def download_file(download_url: str, token: str, dataset_id: str, export_format: str, logger=None):
    """从给定URL下载文件。"""
    log = logger or (lambda msg: print(msg))
    log(f"\n=== Step 3: 下载文件 ===")
    log(f"下载链接: {download_url}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    s = _api_session()
    response = None
    try:
        response = s.get(download_url, headers=headers, stream=True, proxies=_direct_proxies())
        if response.status_code == 200:
            filename = get_filename_from_response(response, download_url, dataset_id, export_format)
            try:
                total_size = int(response.headers.get('content-length', 0)) or None
                with open(filename, 'wb') as f, tqdm(total=total_size, unit='B', unit_scale=True, desc="下载中") as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                file_size = os.path.getsize(filename)
                log(f"✅ 文件已保存: {filename}")
                log(f"📊 文件大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                log(f"📁 保存路径: {os.path.abspath(filename)}")
                return Path(filename)
            except Exception as e:
                log(f"❌ 保存文件失败: {e}")
                return None
        else:
            log(f"❌ 下载失败，状态码: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        log(f"❌ 下载请求异常: {e}")
        return None
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        s.close()


def save_file_content(content: bytes, filename: str, logger=None):
    """保存文件内容到本地磁盘。"""
    log = logger or (lambda msg: print(msg))
    try:
        with open(filename, 'wb') as f:
            f.write(content)
        
        file_size = len(content)
        log(f"✅ 文件已保存: {filename}")
        log(f"📊 文件大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
        log(f"📁 保存路径: {os.path.abspath(filename)}")
        return Path(filename)
        
    except Exception as e:
        log(f"❌ 保存文件失败: {e}")
        return None


def process_downloaded_file(file_path: Path, category_mapping=None, output_dir=None, dir_name=None, logger=None):
    """处理下载的文件：如果是zip则解压，后处理，并重命名目录。"""
    log = logger or (lambda msg: print(msg))
    try:
        if zipfile.is_zipfile(file_path):
            log("📦 检测到 ZIP 压缩包，开始解压...")
            extract_dir = extract_zip(file_path, logger)
            log(f"📁 解压完成，目录: {extract_dir}")

            if file_path.exists():
                file_path.unlink()
                log("🗑️ 已删除原始压缩包")

            processed = rename_coco_in_directory(extract_dir, category_mapping, logger)
            if not processed:
                log("ℹ️ 未触发重命名/重映射。")

            # 如果指定了目录名称，重命名并移动到目标位置
            if dir_name:
                desired_name = dir_name.strip()
                # 去掉.zip扩展名（如果有）
                if desired_name.lower().endswith(".zip"):
                    desired_name = desired_name[:-4]
                
                # 确定目标目录路径
                if output_dir:
                    output_dir_path = Path(output_dir).resolve()
                    target_dir = output_dir_path / desired_name
                else:
                    target_dir = extract_dir.parent / desired_name
                
                # 转换为绝对路径以便比较
                target_dir = target_dir.resolve()
                extract_dir_abs = extract_dir.resolve()
                
                # 如果目标目录已存在，删除它
                if target_dir.exists():
                    if target_dir.is_dir():
                        shutil.rmtree(target_dir)
                    else:
                        target_dir.unlink()
                
                # 如果目标目录和当前目录不在同一位置，需要移动
                if target_dir.parent != extract_dir_abs.parent:
                    shutil.move(str(extract_dir_abs), str(target_dir))
                    log(f"📁 目录已移动到: {target_dir}")
                else:
                    # 在同一父目录下，直接重命名
                    extract_dir_abs.rename(target_dir)
                    log(f"📁 目录已重命名为: {target_dir}")
                return target_dir
            else:
                log(f"📁 处理完成，目录: {extract_dir}")
                return extract_dir
        else:
            log("ℹ️ 非 ZIP 文件，跳过解压与处理。")
            return file_path
    except Exception as exc:
        log(f"❌ 后续处理失败: {exc}")
        return None


def extract_zip(zip_path: Path, logger=None):
    """解压zip文件并返回解压目录。"""
    target_dir = zip_path.parent / zip_path.stem
    suffix = 1
    while target_dir.exists():
        target_dir = zip_path.parent / f"{zip_path.stem}_{suffix}"
        suffix += 1

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_dir)

    return target_dir


def rename_coco_in_directory(directory: Path, category_mapping=None, logger=None):
    """查找COCO标注文件（train/valid/test）并重命名图片。"""
    log = logger or (lambda msg: print(msg))
    target_dirs = []
    for split in ("train", "valid", "test"):
        split_dir = directory / split
        if split_dir.exists() and split_dir.is_dir():
            target_dirs.append(split_dir)

    if not target_dirs:
        target_dirs = [directory]

    processed = False
    for target_dir in target_dirs:
        coco_files = list(target_dir.glob("_annotations.coco.json"))
        if not coco_files:
            continue

        for coco_fp in coco_files:
            current_dir = coco_fp.parent
            log(f"🔍 处理 COCO 标注文件: {coco_fp}")
            try:
                rename_coco_imgnames(current_dir)
                log(f"✅ 重命名完成: {current_dir}")
                if category_mapping:
                    remap_coco_categories(coco_fp, coco_fp, category_mapping)
                    log(f"✅ 类别重映射完成: {coco_fp}")
                processed = True
            except Exception as exc:
                log(f"❌ 重命名失败 ({current_dir}): {exc}")

    if not processed:
        log("ℹ️ 未找到 `_annotations.coco.json`，跳过重命名。")
    return processed


def repack_directory(directory: Path, original_zip_path: Path, output_zip_name=None, logger=None):
    """将处理后的目录重新打包为zip归档文件，使用UTF-8编码。"""
    desired_name = output_zip_name or original_zip_path.stem
    desired_name = desired_name.strip() or original_zip_path.stem

    desired_name = Path(desired_name).name

    if not desired_name.lower().endswith(".zip"):
        desired_name += ".zip"

    target_zip_path = original_zip_path.parent / desired_name

    if target_zip_path.exists():
        target_zip_path.unlink()

    with zipfile.ZipFile(target_zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(directory)
                arcname_str = str(arcname).replace('\\', '/')
                zipf.write(file_path, arcname_str)

    return target_zip_path


def get_filename_from_response(response, url, dataset_id, export_format):
    """从响应或URL获取文件名。"""
    content_disposition = response.headers.get('content-disposition', '')
    if 'filename=' in content_disposition:
        filename = content_disposition.split('filename=')[1].strip('"')
        return filename
    
    parsed_url = urlparse(url)
    if parsed_url.path and '.' in parsed_url.path:
        filename = os.path.basename(parsed_url.path)
        return filename
    
    return f"dataset_{dataset_id}_{export_format}.zip"


def poll_task_status(base_url: str, token: str, task_id: str, max_attempts=30, interval=10, logger=None):
    """轮询任务状态（如果是异步任务）。"""
    log = logger or (lambda msg: print(msg))
    log(f"\n=== 轮询任务状态 ===")
    log(f"任务 ID: {task_id}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    possible_endpoints = [
        f"{base_url}/tasks/{task_id}",
        f"{base_url}/jobs/{task_id}",
        f"{base_url}/exports/{task_id}",
        f"{base_url}/datasets/export_status/{task_id}"
    ]
    
    for endpoint in possible_endpoints:
        try:
            with _api_session() as s:
                response = s.get(endpoint, headers=headers, proxies=_direct_proxies())
                if response.status_code == 200:
                    log(f"✅ 找到可用的任务状态查询接口: {endpoint}")
                    task_data = response.json()
                    log(f"任务信息: {json.dumps(task_data, indent=2)}")
                    return None
        except Exception:
            continue
    
    log("❌ 未找到有效的任务状态查询接口")
    return None


def download_dataset(
    dataset_id: str,
    export_format: str = DEFAULT_FORMAT,
    base_url: str = None,
    username: str = None,
    password: str = None,
    category_mapping: dict = None,
    output_dir: str = None,
    dir_name: str = None,
    logger=None
):
    """
    下载数据集的主函数。
    
    Args:
        dataset_id: 数据集ID
        export_format: 导出格式（默认: coco）
        base_url: API基础URL
        username: API用户名
        password: API密码
        category_mapping: 类别映射字典（可选）
        output_dir: 输出目录（默认: 当前目录）
        dir_name: 最终目录名称（可选，用于重命名处理后的目录，路径为 output_dir / dir_name）
        logger: 日志回调函数（可选）
    
    Returns:
        成功返回最终目录路径，失败返回None
    """
    log = logger or (lambda msg: print(msg))
    log("=== 数据集快照导出工具 ===")
    log(f"数据集 ID: {dataset_id}")
    log(f"导出格式: {export_format}")
    if category_mapping:
        mapping_preview = ", ".join(f"{k}:{v}" for k, v in list(category_mapping.items())[:5])
        if len(category_mapping) > 5:
            mapping_preview += " ..."
        log(f"类别映射已启用: {mapping_preview}")
    else:
        log("类别映射: 未启用")
    if dir_name:
        # 去掉.zip扩展名（如果有）
        final_name = dir_name.strip()
        if final_name.lower().endswith(".zip"):
            final_name = final_name[:-4]
        if output_dir:
            final_path = Path(output_dir) / final_name
            log(f"最终目录路径: {final_path}")
        else:
            log(f"最终目录名称: {final_name}")
    else:
        log("最终目录名称: 使用原始下载文件名")
    
    # 切换到输出目录
    original_cwd = os.getcwd()
    if output_dir:
        output_dir_path = Path(output_dir)
        if not output_dir_path.exists():
            log(f"❌ 输出目录不存在: {output_dir}")
            return None
        if not output_dir_path.is_dir():
            log(f"❌ 输出路径不是目录: {output_dir}")
            return None
        os.chdir(output_dir_path)
    
    try:
        # Step 1: 登录并获取token
        token = login_and_get_token(base_url, username, password, logger)
        if not token:
            log("❌ 无法获取 Token，流程结束")
            return None
        
        # Step 2: 导出数据集快照
        result = export_dataset_snapshot(base_url, token, dataset_id, export_format, logger)
        
        if result is None:
            log("\n❌ 导出失败")
            return None
        
        # 如果返回的是下载URL，需要下载文件
        if isinstance(result, str) and result.startswith('http'):
            result = download_file(result, token, dataset_id, export_format, logger)
        
        # 如果返回的是文件路径，需要处理文件
        if isinstance(result, Path):
            final_path = process_downloaded_file(
                result,
                category_mapping=category_mapping,
                output_dir=output_dir,
                dir_name=dir_name,
                logger=logger
            )
            if final_path:
                log(f"📁 最终目录位置: {final_path}")
                log("\n🎉 导出完成！")
                return final_path
        
        log("\n❌ 导出失败")
        return None
        
    finally:
        os.chdir(original_cwd)


def main():
    """CLI入口点。"""
    parser = argparse.ArgumentParser(
        description="数据集快照导出工具（CLI版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s 12345
  %(prog)s 12345 --format coco --output-dir ./datasets
  %(prog)s 12345 --dir-name my_dataset --output-dir ./datasets --category-group my_model
        """
    )
    
    parser.add_argument(
        "dataset_id",
        type=str,
        help="数据集ID"
    )
    
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        default=DEFAULT_FORMAT,
        help=f"导出格式（默认: {DEFAULT_FORMAT}）"
    )
    
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="输出目录（默认: 当前目录）"
    )
    
    parser.add_argument(
        "--dir-name",
        "-d",
        type=str,
        default=None,
        help="最终目录名称（处理完成后将目录重命名为该名称，路径为 output_dir / dir_name）"
    )
    
    parser.add_argument(
        "--category-group",
        "-c",
        type=str,
        default=None,
        help="类别映射组名称（从.config文件中读取）"
    )
    
    args = parser.parse_args()
    
    # 加载配置
    try:
        base_url, username, password, category_groups = load_api_credentials()
    except Exception as e:
        print(f"❌ 配置错误: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 获取类别映射
    category_mapping = None
    if args.category_group:
        if args.category_group not in category_groups:
            print(f"❌ 类别映射组 '{args.category_group}' 不存在", file=sys.stderr)
            print(f"可用的类别映射组: {', '.join(category_groups.keys())}", file=sys.stderr)
            sys.exit(1)
        category_mapping = category_groups[args.category_group]
    
    # 执行下载
    result = download_dataset(
        dataset_id=args.dataset_id,
        export_format=args.format,
        base_url=base_url,
        username=username,
        password=password,
        category_mapping=category_mapping,
        output_dir=args.output_dir,
        dir_name=args.dir_name
    )
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
