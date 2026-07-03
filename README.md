# DiffTestGen: Change-Directed LLM-Based Testing for Exposing Behavioral Differences

DiffTestGen, a change-directed, LLM-based differential testing approach to expose behavioral differences introduced by code changes.

## Set up
DiffTestGen uses two kinds of Docker containers:

* A Visual Studio Code Dev Container for running DiffTestGen itself. See [devcontainer.json](.devcontainer/devcontainer.json).

* Docker-in-docker containers for target projects to analyze with testora. These containers are created when creating the dev container. See [postCreateCommands.sh](.devcontainer/postCreateCommands.sh).

To build the containers, follow these steps:

1) Install [Visual Studio Code](https://code.visualstudio.com/download) and its ["Dev Containers" extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).

2) Open DiffTestGen in Visual Studio Code.

3) In Visual Studio Code, build the Dev Container and reopen the project in the container (This will take a couple of minutes):

    ```Ctrl + Shift + P```

    ```Dev Containers: Rebuild and Reopen in Container```

To run DiffTestGen, create key files in the main directory:
1)  `.openai_token` with an OpenAI API key. This is required for invoking an LLM, which is an essential part of testora.

2) `.github_token` with a (free to create) GitHub API key. This is required because DiffTestGen interacts with the GitHub API to retrieve details about the PRs to analyze.

## Running DiffTestGen
_**Note:** Since DiffTestGen is implemented on top of Testora, some implementation artifacts still retain the Testora name._

Main source file: [testora.RegressionFinder](src/testora/RegressionFinder.py).
To run the main souce file, we provide two entry files (**select one to run**), each corresponds to a mode, database mode and local mode, respectively:   

1) **[Database mode]** Entry file [testora.Entry](src/testora/Entry.py) allows to run in database mode, which fetches PRs to check from the database and applies the approach to each PR. The result logs will be write into the database. Assuming you have set up the database, to run it:  

    ```python -m testora.Entry```  

    **To check the status of PRs:**

    ```python -m testora.evaluation.EvalTaskManager --status```

    **To download results:**  
    Once some or all PRs have been analyzed, download the results from the database:

    ```python -m testora.evaluation.EvalTaskManager --fetch```

2) **[Local mode]** Entry file [testora.EntryLocal](src/testora/EntryLocal.py) allows to run at local, without setting up the database. The result logs will be write into the root folder of this project. To run it:

    ```python -m testora.EntryLocal```


Overall, to run DiffTestGen:  
1) We have multiple files starts with \`Entry\', each such `Entry'-prefix file uses a similar inner logic, but serves for a different purpose.
    * [testora.Entry](src/testora/Entry.py) 
        * To run DiffTestGen in database mode on Testora data. 
        * Check code implementation for more detailed setting, supports running experiments for entire abaltion study or a specific configuration, e.g, DiffTestGen. 
    * [testora.EntryLocal](src/testora/EntryLocal.py) 
        * To run DiffTestGen at local on Testora data. 
        * Also supports entire abaltion study or a specific configuration.
    * [testora.EntryLocalChaCo](src/testora/EntryLocalChaCo.py) 
        * To run DiffTestGen at local on ChaCo data.
    * [testora.EntryLocalClassification](src/testora/EntryLocalClassification.py)   
        * To run classification on specified log files.
2) Supports parallel running for these `Entry'-prefix files in different Dev Containers.
    <!-- Example 1: run [testora.Entry](src/testora/Entry.py) in marshmallow container -->

## Inspecting Results in the Web UI

We provide a Web UI to inspect detailed logs.

1) Launch the web server:

    ```python -m testora.webui.WebUI --files logs_*.json```

2) Visit [http://localhost:4000/](http://localhost:4000/) in your browser.

3) Click to inspect the detailed logs of a PR.


## Results Reported in the Paper 
<!-- Overall, to run the experiments:  
* For RQ1 and RQ2:

    ```
    python -m testora.Entry
    python -m testora.EntryLocalChaCo
    ```

* For RQ4:
    ```
    python -m testora.EntryLocalClassification
    ``` -->

**Notes:**
* All result log files are in [data/results/gpt-5-mini-2025-08-07](data/results/gpt-5-mini-2025-08-07) and [data/results/gpt-4o-mini-2024-07-18](data/results/gpt-4o-mini-2024-07-18).
* Classification log files are in [data/results/classification](data/results/classification).
* All figures and tables are in [data/results/table_and_plots](data/results/table_and_plots).
### RQ1 Effectiveness and RQ2 Component Contributions
* To run the experiments:
    ```
    python -m testora.Entry
    python -m testora.EntryLocalChaCo
    ```

* To analysis and visualize the results:  
    **1) On Testora data**  
    * [PRs with different outputs] Run [src/testora/analysis/DifferentOutputsStatistics](src/testora/analysis/DifferentOutputsStatistics)
        * --> Figure 5a, last column of Table IV
    * [Union coverage] Run [src/testora/visualization/PlotCoverageAblation.py](src/testora/visualization/PlotCoverageAblation.py)
        * --> Figure 5b
    * [Number of generated tests] Run [src/testora/analysis/GeneratedTestsStatistics.py](src/testora/analysis/GeneratedTestsStatistics.py)
        * --> Table IV (exclude last column)

    **2) On ChaCo data** 
    * [PRs with different outputs] Run [src/testora/analysis/DifferentOutputsStatisticsChaCo](src/testora/analysis/DifferentOutputsStatisticsChaCo)
        * --> To form the $Num_{PR}$ part of Table V
    * [Union coverage] Run [src/testora/visualization/PlotCoverageAblation.py](src/testora/visualization/PlotCoverageChaCo.py)
        * --> To form the $Cov_{union}$ part of Table V 
    
### 
### RQ3: Efficiency
* Set the _name_ and _base\_dir_ at the top part of [src/testora/evaluation/PRAnalysisStats.py](src/testora/evaluation/PRAnalysisStats.py) and run it to get the corresponding cost meta information.  
    * --> The output information forms TABLE VI

<!-- For Testora, DifftestGen:
```
name = "testora" # "testora" or "difftestgen"
base_dir = f"data/results/gpt-5-mini-2025-08-07/iter_0/log_{name}/"
``` -->

<!-- For Testora++, 
```
name = "testora"
base_dir = f"data/results/gpt-5-mini-2025-08-07/iter_0_100/log_{name}/"
``` -->

### RQ4: Usefulness
* To get the $Num_{PR}$ and $Num_{test}$ in Table VII:  
    * Run [src/testora/analysis/DifferentOutputsStatistics](src/testora/analysis/DifferentOutputsStatistics) on the 70 PRs (recorded in [data/meta/pr_classifier](data/meta/pr_classifier))

* To run the classification and get the $Num_{test}^{clarify}$ and $Num_{PR}^{regression}$ in Table VII:  
    * ```python -m testora.EntryLocalClassification```         
    * Run [src/testora/analysis/ClassificationStatistics.py](src/testora/analysis/ClassificationStatistics.py)
