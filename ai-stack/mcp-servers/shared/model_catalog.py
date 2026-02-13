#!/usr/bin/env python3
"""
Hardware-Tier Model Catalog for AI Stack Services

Implements a model catalog with hardware budget enforcement and automatic
model selection based on available resources.
"""

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import psutil


logger = logging.getLogger(__name__)


class HardwareTier(Enum):
    """Hardware tiers based on system capabilities"""
    CPU_ONLY = "cpu_only"
    IGPU = "igpu"  # Integrated GPU
    LOW_VRAM_GPU = "low_vram_gpu"  # 4-8GB VRAM
    MID_VRAM_GPU = "mid_vram_gpu"   # 8-16GB VRAM
    HIGH_VRAM_GPU = "high_vram_gpu"  # 16-24GB VRAM
    VERY_HIGH_VRAM_GPU = "very_high_vram_gpu"  # 24GB+ VRAM


class ModelSize(Enum):
    """Model size categories"""
    SMALL = "small"      # < 2B parameters
    MEDIUM = "medium"    # 2-7B parameters  
    LARGE = "large"      # 7-14B parameters
    XLARGE = "xlarge"    # 14-32B parameters
    XXLARGE = "xxlarge"  # 32B+ parameters


@dataclass
class ModelSpec:
    """Specification for an AI model"""
    name: str
    display_name: str
    size: ModelSize
    vram_requirement_gb: float
    cpu_ram_requirement_gb: float
    expected_vram_usage_gb: float  # Actual usage during inference
    expected_cpu_ram_usage_gb: float  # Actual usage during inference
    expected_tps: float  # Tokens per second
    expected_quality_score: float  # 0.0-1.0
    hardware_tier: HardwareTier
    tags: List[str]
    description: str
    license: str
    quantization_support: bool = True
    recommended_quantization: Optional[str] = None  # e.g., "Q4_K_M", "Q5_K_S"
    

@dataclass
class HardwareProfile:
    """Detected hardware profile of the system"""
    cpu_cores: int
    total_ram_gb: float
    available_ram_gb: float
    gpu_present: bool
    gpu_name: Optional[str]
    gpu_vram_total_gb: Optional[float]
    gpu_vram_available_gb: Optional[float]
    cuda_available: bool
    rocm_available: bool
    hardware_tier: HardwareTier
    recommended_models: List[str]


class ModelCatalog:
    """Catalog of available models with hardware compatibility"""
    
    def __init__(self):
        self.models: Dict[str, ModelSpec] = {}
        self._load_default_models()
    
    def _load_default_models(self):
        """Load default model specifications"""
        default_models = [
            # CPU/iGPU models
            ModelSpec(
                name="microsoft/Phi-3-mini-4k-instruct",
                display_name="Phi-3 Mini",
                size=ModelSize.SMALL,
                vram_requirement_gb=2.0,
                cpu_ram_requirement_gb=4.0,
                expected_vram_usage_gb=1.5,
                expected_cpu_ram_usage_gb=3.0,
                expected_tps=60.0,
                expected_quality_score=0.68,
                hardware_tier=HardwareTier.CPU_ONLY,
                tags=["code", "small", "fast", "budget"],
                description="Lightweight model suitable for CPU-only or low VRAM systems",
                license="MIT",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            ModelSpec(
                name="microsoft/Phi-3-small-8k-instruct",
                display_name="Phi-3 Small",
                size=ModelSize.MEDIUM,
                vram_requirement_gb=3.0,
                cpu_ram_requirement_gb=6.0,
                expected_vram_usage_gb=2.5,
                expected_cpu_ram_usage_gb=5.0,
                expected_tps=45.0,
                expected_quality_score=0.72,
                hardware_tier=HardwareTier.IGPU,
                tags=["code", "small", "balanced"],
                description="Balanced model for integrated GPUs",
                license="MIT",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            
            # Low VRAM GPU models (4-8GB)
            ModelSpec(
                name="Qwen/Qwen2.5-Coder-3B-Instruct",
                display_name="Qwen2.5-Coder-3B",
                size=ModelSize.MEDIUM,
                vram_requirement_gb=4.0,
                cpu_ram_requirement_gb=8.0,
                expected_vram_usage_gb=3.5,
                expected_cpu_ram_usage_gb=6.0,
                expected_tps=50.0,
                expected_quality_score=0.75,
                hardware_tier=HardwareTier.LOW_VRAM_GPU,
                tags=["code", "medium", "efficient"],
                description="Efficient coding model for low VRAM GPUs",
                license="Apache-2.0",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            
            # Mid VRAM GPU models (8-16GB)
            ModelSpec(
                name="Qwen/Qwen2.5-Coder-7B-Instruct",
                display_name="Qwen2.5-Coder-7B",
                size=ModelSize.LARGE,
                vram_requirement_gb=8.0,
                cpu_ram_requirement_gb=12.0,
                expected_vram_usage_gb=7.0,
                expected_cpu_ram_usage_gb=10.0,
                expected_tps=40.0,
                expected_quality_score=0.88,
                hardware_tier=HardwareTier.MID_VRAM_GPU,
                tags=["code", "large", "high_quality"],
                description="High-quality coding model for mid-range GPUs",
                license="Apache-2.0",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            ModelSpec(
                name="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
                display_name="DeepSeek-Coder-V2-Lite",
                size=ModelSize.LARGE,
                vram_requirement_gb=10.0,
                cpu_ram_requirement_gb=16.0,
                expected_vram_usage_gb=9.0,
                expected_cpu_ram_usage_gb=14.0,
                expected_tps=35.0,
                expected_quality_score=0.81,
                hardware_tier=HardwareTier.MID_VRAM_GPU,
                tags=["code", "algorithm", "multilingual"],
                description="Algorithm-focused model for complex problem solving",
                license="Apache-2.0",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            
            # High VRAM GPU models (16-24GB)
            ModelSpec(
                name="Qwen/Qwen2.5-Coder-14B-Instruct",
                display_name="Qwen2.5-Coder-14B",
                size=ModelSize.XLARGE,
                vram_requirement_gb=16.0,
                cpu_ram_requirement_gb=24.0,
                expected_vram_usage_gb=14.0,
                expected_cpu_ram_usage_gb=20.0,
                expected_tps=30.0,
                expected_quality_score=0.89,
                hardware_tier=HardwareTier.HIGH_VRAM_GPU,
                tags=["code", "xl", "production"],
                description="Production-ready model for complex coding tasks",
                license="Apache-2.0",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            ModelSpec(
                name="codellama/CodeLlama-13b-Instruct-hf",
                display_name="CodeLlama-13B",
                size=ModelSize.XLARGE,
                vram_requirement_gb=16.0,
                cpu_ram_requirement_gb=24.0,
                expected_vram_usage_gb=14.5,
                expected_cpu_ram_usage_gb=22.0,
                expected_tps=25.0,
                expected_quality_score=0.78,
                hardware_tier=HardwareTier.HIGH_VRAM_GPU,
                tags=["code", "legacy", "well_tested"],
                description="Well-tested legacy model for reliable performance",
                license="Meta-Llama-License",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            
            # Very High VRAM GPU models (24GB+)
            ModelSpec(
                name="deepseek-ai/DeepSeek-Coder-V2-Instruct",
                display_name="DeepSeek-Coder-V2",
                size=ModelSize.XXLARGE,
                vram_requirement_gb=24.0,
                cpu_ram_requirement_gb=32.0,
                expected_vram_usage_gb=22.0,
                expected_cpu_ram_usage_gb=30.0,
                expected_tps=20.0,
                expected_quality_score=0.84,
                hardware_tier=HardwareTier.VERY_HIGH_VRAM_GPU,
                tags=["code", "xxl", "reasoning"],
                description="Advanced reasoning model for complex problems",
                license="Apache-2.0",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            ),
            ModelSpec(
                name="meta-llama/Meta-Llama-3-70B-Instruct",
                display_name="Llama-3-70B",
                size=ModelSize.XXLARGE,
                vram_requirement_gb=40.0,
                cpu_ram_requirement_gb=64.0,
                expected_vram_usage_gb=38.0,
                expected_cpu_ram_usage_gb=60.0,
                expected_tps=15.0,
                expected_quality_score=0.92,
                hardware_tier=HardwareTier.VERY_HIGH_VRAM_GPU,
                tags=["general", "xxl", "state_of_art"],
                description="State-of-the-art general purpose model",
                license="Meta-Llama-License",
                quantization_support=True,
                recommended_quantization="Q4_K_M"
            )
        ]
        
        for model in default_models:
            self.models[model.name] = model
    
    def get_models_for_hardware_tier(self, tier: HardwareTier) -> List[ModelSpec]:
        """Get all models compatible with a specific hardware tier"""
        return [model for model in self.models.values() if model.hardware_tier == tier]
    
    def get_models_by_size(self, size: ModelSize) -> List[ModelSpec]:
        """Get all models of a specific size"""
        return [model for model in self.models.values() if model.size == size]
    
    def get_model_by_name(self, name: str) -> Optional[ModelSpec]:
        """Get a specific model by name"""
        return self.models.get(name)
    
    def get_recommended_models_for_hardware(self, hardware_profile: HardwareProfile) -> List[ModelSpec]:
        """Get recommended models for a specific hardware profile"""
        compatible_models = self.get_models_for_hardware_tier(hardware_profile.hardware_tier)
        
        # Filter by actual available resources
        filtered_models = []
        for model in compatible_models:
            if (hardware_profile.available_ram_gb >= model.cpu_ram_requirement_gb and
                (not hardware_profile.gpu_present or 
                 hardware_profile.gpu_vram_available_gb is None or
                 hardware_profile.gpu_vram_available_gb >= model.vram_requirement_gb)):
                filtered_models.append(model)
        
        # Sort by quality score descending
        filtered_models.sort(key=lambda m: m.expected_quality_score, reverse=True)
        return filtered_models
    
    def get_all_models(self) -> List[ModelSpec]:
        """Get all models in the catalog"""
        return list(self.models.values())


class HardwareDetector:
    """Detects hardware capabilities and determines system profile"""
    
    def __init__(self):
        pass
    
    def detect_hardware_profile(self) -> HardwareProfile:
        """Detect the current hardware profile"""
        # Detect CPU info
        cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        available_ram_gb = psutil.virtual_memory().available / (1024**3)
        
        # Detect GPU info
        gpu_present = False
        gpu_name = None
        gpu_vram_total_gb = None
        gpu_vram_available_gb = None
        cuda_available = False
        rocm_available = False
        
        # Check for NVIDIA GPU
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                gpu_info = result.stdout.strip().split(', ')
                gpu_name = gpu_info[0].strip()
                gpu_vram_total_gb = float(gpu_info[1].strip()) / 1024.0  # Convert MB to GB
                gpu_vram_available_gb = gpu_vram_total_gb * 0.9  # Assume 90% available initially
                gpu_present = True
                cuda_available = True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError, IndexError, ValueError):
            pass
        
        # Check for AMD GPU if NVIDIA not found
        if not gpu_present:
            try:
                result = subprocess.run(['rocm-smi', '--showmeminfo', 'vram', '--csv'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and 'vram' in result.stdout.lower():
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        values = lines[1].split(',')
                        gpu_vram_total_gb = float(values[1].strip()) / 1024.0  # Convert MB to GB
                        gpu_vram_available_gb = gpu_vram_total_gb * 0.9  # Assume 90% available initially
                        gpu_name = "AMD GPU"
                        gpu_present = True
                        rocm_available = True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError, IndexError, ValueError):
                pass
        
        # Determine hardware tier
        hardware_tier = self._determine_hardware_tier(
            cpu_cores, total_ram_gb, gpu_present, gpu_vram_total_gb
        )
        
        return HardwareProfile(
            cpu_cores=cpu_cores,
            total_ram_gb=round(total_ram_gb, 2),
            available_ram_gb=round(available_ram_gb, 2),
            gpu_present=gpu_present,
            gpu_name=gpu_name,
            gpu_vram_total_gb=round(gpu_vram_total_gb, 2) if gpu_vram_total_gb else None,
            gpu_vram_available_gb=round(gpu_vram_available_gb, 2) if gpu_vram_available_gb else None,
            cuda_available=cuda_available,
            rocm_available=rocm_available,
            hardware_tier=hardware_tier,
            recommended_models=[]  # Will be populated separately
        )
    
    def _determine_hardware_tier(self, cpu_cores: int, total_ram_gb: float, 
                                 gpu_present: bool, gpu_vram_gb: Optional[float]) -> HardwareTier:
        """Determine hardware tier based on system specs"""
        if gpu_vram_gb is not None:
            if gpu_vram_gb >= 24:
                return HardwareTier.VERY_HIGH_VRAM_GPU
            elif gpu_vram_gb >= 16:
                return HardwareTier.HIGH_VRAM_GPU
            elif gpu_vram_gb >= 8:
                return HardwareTier.MID_VRAM_GPU
            else:
                return HardwareTier.LOW_VRAM_GPU
        elif gpu_present:
            # Integrated GPU or unknown VRAM
            if total_ram_gb >= 16:
                return HardwareTier.IGPU
            else:
                return HardwareTier.CPU_ONLY
        else:
            # CPU only
            return HardwareTier.CPU_ONLY


class ModelSelector:
    """Selects appropriate models based on hardware and requirements"""
    
    def __init__(self, catalog: ModelCatalog, hardware_detector: HardwareDetector):
        self.catalog = catalog
        self.hardware_detector = hardware_detector
    
    def get_current_hardware_profile(self) -> HardwareProfile:
        """Get the current hardware profile"""
        profile = self.hardware_detector.detect_hardware_profile()
        
        # Get recommended models for this hardware
        recommended_models = self.catalog.get_recommended_models_for_hardware(profile)
        profile.recommended_models = [model.name for model in recommended_models]
        
        return profile
    
    def select_best_model(self, task_requirements: Optional[Dict[str, Any]] = None) -> Optional[ModelSpec]:
        """Select the best model based on hardware and optional task requirements"""
        hardware_profile = self.get_current_hardware_profile()
        
        # Get compatible models
        compatible_models = self.catalog.get_recommended_models_for_hardware(hardware_profile)
        
        if not compatible_models:
            logger.warning("No compatible models found for current hardware")
            return None
        
        # Apply task requirements filter if provided
        if task_requirements:
            filtered_models = []
            for model in compatible_models:
                meets_requirements = True
                
                # Check tags if specified
                required_tags = task_requirements.get('required_tags', [])
                if required_tags:
                    for req_tag in required_tags:
                        if req_tag not in model.tags:
                            meets_requirements = False
                            break
                
                # Check minimum quality if specified
                min_quality = task_requirements.get('min_quality_score')
                if min_quality and model.expected_quality_score < min_quality:
                    meets_requirements = False
                
                # Check minimum TPS if specified
                min_tps = task_requirements.get('min_tps')
                if min_tps and model.expected_tps < min_tps:
                    meets_requirements = False
                
                if meets_requirements:
                    filtered_models.append(model)
            
            compatible_models = filtered_models
        
        if not compatible_models:
            logger.warning("No models meet the specified task requirements")
            return None
        
        # Select the highest quality model that fits the hardware tier
        best_model = max(compatible_models, key=lambda m: m.expected_quality_score)
        return best_model
    
    def get_model_recommendations(self, hardware_tier: Optional[HardwareTier] = None) -> List[ModelSpec]:
        """Get model recommendations, optionally for a specific hardware tier"""
        if hardware_tier:
            return self.catalog.get_models_for_hardware_tier(hardware_tier)
        else:
            hardware_profile = self.get_current_hardware_profile()
            return self.catalog.get_recommended_models_for_hardware(hardware_profile)


class ModelCatalogManager:
    """Manager for the model catalog with hardware awareness"""
    
    def __init__(self):
        self.catalog = ModelCatalog()
        self.hardware_detector = HardwareDetector()
        self.selector = ModelSelector(self.catalog, self.hardware_detector)
    
    def get_hardware_profile(self) -> HardwareProfile:
        """Get the current hardware profile"""
        return self.selector.get_current_hardware_profile()
    
    def get_available_models(self) -> List[ModelSpec]:
        """Get all available models"""
        return self.catalog.get_all_models()
    
    def get_compatible_models(self) -> List[ModelSpec]:
        """Get models compatible with current hardware"""
        hardware_profile = self.get_hardware_profile()
        return self.catalog.get_recommended_models_for_hardware(hardware_profile)
    
    def recommend_model(self, task_requirements: Optional[Dict[str, Any]] = None) -> Optional[ModelSpec]:
        """Recommend the best model for the current hardware and task"""
        return self.selector.select_best_model(task_requirements)
    
    def validate_model_selection(self, model_name: str) -> Dict[str, Any]:
        """Validate if a model selection is appropriate for current hardware"""
        model = self.catalog.get_model_by_name(model_name)
        if not model:
            return {
                "valid": False,
                "reason": f"Model {model_name} not found in catalog"
            }
        
        hardware_profile = self.get_hardware_profile()
        
        # Check hardware tier compatibility
        if model.hardware_tier.value != hardware_profile.hardware_tier.value:
            return {
                "valid": False,
                "reason": f"Model tier {model.hardware_tier.value} incompatible with system tier {hardware_profile.hardware_tier.value}",
                "suggestion": f"Consider models for {hardware_profile.hardware_tier.value} tier"
            }
        
        # Check RAM requirements
        if hardware_profile.available_ram_gb < model.cpu_ram_requirement_gb:
            return {
                "valid": False,
                "reason": f"Insufficient RAM: need {model.cpu_ram_requirement_gb}GB, have {hardware_profile.available_ram_gb}GB",
                "suggestion": f"Free up {model.cpu_ram_requirement_gb - hardware_profile.available_ram_gb}GB or select smaller model"
            }
        
        # Check VRAM requirements if GPU is present
        if (hardware_profile.gpu_present and 
            hardware_profile.gpu_vram_available_gb is not None and
            hardware_profile.gpu_vram_available_gb < model.vram_requirement_gb):
            return {
                "valid": False,
                "reason": f"Insufficient VRAM: need {model.vram_requirement_gb}GB, have {hardware_profile.gpu_vram_available_gb}GB",
                "suggestion": f"Select model requiring <={hardware_profile.gpu_vram_available_gb}GB VRAM"
            }
        
        return {
            "valid": True,
            "reason": "Model selection is appropriate for current hardware",
            "expected_performance": {
                "tps": model.expected_tps,
                "quality_score": model.expected_quality_score,
                "vram_usage_gb": model.expected_vram_usage_gb,
                "ram_usage_gb": model.expected_cpu_ram_usage_gb
            }
        }
    
    def get_catalog_summary(self) -> Dict[str, Any]:
        """Get a summary of the model catalog"""
        all_models = self.get_available_models()
        
        summary = {
            "total_models": len(all_models),
            "by_tier": {},
            "by_size": {},
            "hardware_profile": self.get_hardware_profile().__dict__,
            "compatible_models_count": len(self.get_compatible_models())
        }
        
        # Count by tier
        for model in all_models:
            tier = model.hardware_tier.value
            summary["by_tier"][tier] = summary["by_tier"].get(tier, 0) + 1
        
        # Count by size
        for model in all_models:
            size = model.size.value
            summary["by_size"][size] = summary["by_size"].get(size, 0) + 1
        
        return summary


# Example usage
async def example_usage():
    """Example of how to use the hardware-tier model catalog"""
    
    # Create the manager
    manager = ModelCatalogManager()
    
    # Get hardware profile
    hardware_profile = manager.get_hardware_profile()
    print("Hardware Profile:")
    print(f"  CPU Cores: {hardware_profile.cpu_cores}")
    print(f"  Total RAM: {hardware_profile.total_ram_gb}GB")
    print(f"  Available RAM: {hardware_profile.available_ram_gb}GB")
    print(f"  GPU Present: {hardware_profile.gpu_present}")
    if hardware_profile.gpu_name:
        print(f"  GPU: {hardware_profile.gpu_name}")
        print(f"  GPU VRAM: {hardware_profile.gpu_vram_total_gb}GB")
    print(f"  Hardware Tier: {hardware_profile.hardware_tier.value}")
    print(f"  Recommended Models: {hardware_profile.recommended_models[:3]}...")  # Show first 3
    print()
    
    # Get catalog summary
    summary = manager.get_catalog_summary()
    print("Catalog Summary:")
    print(f"  Total Models: {summary['total_models']}")
    print(f"  Compatible Models: {summary['compatible_models_count']}")
    print(f"  By Tier: {summary['by_tier']}")
    print(f"  By Size: {summary['by_size']}")
    print()
    
    # Get compatible models
    compatible_models = manager.get_compatible_models()
    print(f"Compatible Models ({len(compatible_models)}):")
    for model in compatible_models[:5]:  # Show first 5
        print(f"  - {model.display_name} ({model.size.value}): {model.expected_quality_score:.2f} quality, {model.expected_tps:.1f} TPS")
    print()
    
    # Recommend a model for a specific task
    task_requirements = {
        "required_tags": ["code"],
        "min_quality_score": 0.7,
        "min_tps": 30
    }
    recommended_model = manager.recommend_model(task_requirements)
    if recommended_model:
        print(f"Recommended Model for Task: {recommended_model.display_name}")
        print(f"  Quality Score: {recommended_model.expected_quality_score}")
        print(f"  Expected TPS: {recommended_model.expected_tps}")
        print(f"  VRAM Requirement: {recommended_model.vram_requirement_gb}GB")
    else:
        print("No suitable model found for the task requirements")
    print()
    
    # Validate a model selection
    if compatible_models:
        model_to_validate = compatible_models[0].name
        validation = manager.validate_model_selection(model_to_validate)
        print(f"Validation for {model_to_validate}:")
        print(f"  Valid: {validation['valid']}")
        print(f"  Reason: {validation['reason']}")
        if validation['valid'] and 'expected_performance' in validation:
            perf = validation['expected_performance']
            print(f"  Expected TPS: {perf['tps']}")
            print(f"  Quality Score: {perf['quality_score']}")


if __name__ == "__main__":
    asyncio.run(example_usage())